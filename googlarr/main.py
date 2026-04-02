import traceback
import asyncio
import os
import time
import threading
from datetime import datetime, timedelta
from croniter import croniter

from plexapi.server import PlexServer
from googlarr.config import load_config, validate_config
from googlarr.db import (
    init_db,
    sync_library_with_plex,
    claim_next_poster_task,
    update_item_status,
    get_items_for_update,
    reset_working_tasks
)
from googlarr.prank import (
    download_poster,
    generate_prank_poster,
    set_poster,
    initialize_detector_and_overlay,
    apply_pranks,
    restore_originals
)

# --- CONFIG ---
SYNC_INTERVAL_MINUTES = 360
POSTER_WORKERS = 1
WORKER_IDLE_SLEEP_SECONDS = 30
MAX_SLEEP_SECONDS = 60  # Cap on sleep duration to stay responsive

# --- GLOBAL CONFIG RELOAD EVENT ---
CONFIG_RELOAD_EVENT = asyncio.Event()
_main_loop = None  # Reference to running event loop for thread-safe signalling


def is_prank_active(config):
    """Check if we are currently inside the prank window."""
    now = datetime.now()
    cron_on = croniter(config['schedule']['start'], now)
    cron_off = croniter(config['schedule']['stop'], now)

    last_on = cron_on.get_prev(datetime)
    last_off = cron_off.get_prev(datetime)

    # If the last start time is after the last stop time, we're in a prank window
    return last_on > last_off


async def sync_task(config, plex):
    while True:
        try:
            # Reload config at start of each iteration
            config = load_config()
            validate_config(config)
        except ValueError as e:
            print(f"[SYNC] Config validation failed: {e}. Using previous config.")

        print("[SYNC] Syncing library with Plex...")
        try:
            sync_library_with_plex(config, plex)
        except Exception as e:
            print(f"[SYNC] Sync error: {e}")

        # Sleep for interval, but check for reload event every MAX_SLEEP_SECONDS
        sleep_duration = SYNC_INTERVAL_MINUTES * 60
        while sleep_duration > 0:
            try:
                await asyncio.wait_for(
                    CONFIG_RELOAD_EVENT.wait(),
                    timeout=min(sleep_duration, MAX_SLEEP_SECONDS)
                )
                # Event was set - config reload requested
                print("[SYNC] Config reload requested")
                CONFIG_RELOAD_EVENT.clear()
                break  # Re-enter outer loop to reload config
            except asyncio.TimeoutError:
                # Normal timeout, continue sleeping
                sleep_duration -= MAX_SLEEP_SECONDS


async def poster_worker(worker_id, config, plex):
    while True:
        try:
            # Reload config periodically
            config = load_config()
            validate_config(config)
        except ValueError as e:
            print(f"[POSTER-{worker_id}] Config validation failed: {e}. Using previous config.")

        item = claim_next_poster_task(config['database'])

        if not item:
            print(f"[POSTER-{worker_id}] Sleeping...")
            try:
                await asyncio.wait_for(
                    CONFIG_RELOAD_EVENT.wait(),
                    timeout=WORKER_IDLE_SLEEP_SECONDS
                )
                # Event was set
                CONFIG_RELOAD_EVENT.clear()
                print(f"[POSTER-{worker_id}] Config reload signaled")
            except asyncio.TimeoutError:
                # Normal timeout
                pass
            continue

        print(f"[POSTER-{worker_id}] Working on item {item['title']} ({item['status']})")

        try:
            if item['status'] == 'WORKING_DOWNLOAD':
                await asyncio.to_thread(download_poster, plex, item, item['original_path'], config)
                update_item_status(config['database'], item['item_id'], 'ORIGINAL_DOWNLOADED')

            elif item['status'] == 'WORKING_PRANKIFY':
                await asyncio.to_thread(generate_prank_poster, item['original_path'], item['prank_path'], config)
                update_item_status(config['database'], item['item_id'], 'PRANK_GENERATED')

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[POSTER-{worker_id}] Error processing {item['title']}: {e.__class__.__name__}: {e}")
            print(tb)

            update_item_status(config['database'], item['item_id'], 'FAILED')


async def update_posters_task(config, plex):
    print("[UPDATE] Starting cron-driven poster updater")

    # Handle startup state: check if prank window is currently active
    prank_active = is_prank_active(config)
    print(f"[UPDATE] At startup, prank window is {'ACTIVE' if prank_active else 'INACTIVE'}")

    if prank_active:
        print("[UPDATE] Applying any ready pranks from startup...")
        count = apply_pranks(config, plex)
        print(f"[UPDATE] Applied {count} prank poster(s) at startup")
    else:
        print("[UPDATE] Restoring any pranked posters from startup...")
        count = restore_originals(config, plex)
        print(f"[UPDATE] Restored {count} original poster(s) at startup")

    while True:
        try:
            # Reload config at start of each iteration
            config = load_config()
            validate_config(config)
        except ValueError as e:
            print(f"[UPDATE] Config validation failed: {e}. Using previous config.")

        now = datetime.now()

        cron_on = croniter(config['schedule']['start'], now)
        cron_off = croniter(config['schedule']['stop'], now)

        next_on = cron_on.get_next(datetime)
        next_off = cron_off.get_next(datetime)

        print(f"[UPDATE] Next on: {next_on}. Next off: {next_off}")

        # Decide which event is next
        if next_on < next_off:
            next_event = next_on
            action = "apply"
        else:
            next_event = next_off
            action = "restore"

        sleep_duration = (next_event - now).total_seconds()
        sleep_duration = min(sleep_duration, MAX_SLEEP_SECONDS)  # Cap at MAX_SLEEP_SECONDS

        print(f"[UPDATE] Next action: {action.upper()} at {next_event}. Sleeping for {sleep_duration:.0f} seconds...")

        try:
            # Sleep OR wait for reload event
            await asyncio.wait_for(
                CONFIG_RELOAD_EVENT.wait(),
                timeout=sleep_duration
            )
            # Event was set - config reload requested
            print("[UPDATE] Config reload requested, recalculating schedule...")
            CONFIG_RELOAD_EVENT.clear()
            continue  # Recalculate schedule immediately

        except asyncio.TimeoutError:
            # Normal timeout, check if it's time to act
            pass

        # Check if it's time to apply/restore
        now = datetime.now()
        if now >= next_event:
            if action == "apply":
                count = apply_pranks(config, plex)
                print(f"[UPDATE] Applied {count} prank poster(s)")
            else:
                count = restore_originals(config, plex)
                print(f"[UPDATE] Restored {count} original poster(s)")



def signal_config_reload():
    """Signal all tasks to reload config. Thread-safe — callable from Flask or anywhere."""
    global _main_loop
    if _main_loop is not None and _main_loop.is_running():
        _main_loop.call_soon_threadsafe(CONFIG_RELOAD_EVENT.set)
    else:
        CONFIG_RELOAD_EVENT.set()
    print("[MAIN] Config reload signal sent to all tasks")


async def main():
    global _main_loop
    _main_loop = asyncio.get_running_loop()

    config = load_config()
    validate_config(config)
    init_db(config['database'])
    reset_working_tasks(config['database'])
    initialize_detector_and_overlay(config['detection'])
    plex = PlexServer(config['plex']['url'], config['plex']['token'])

    # Start web server in separate thread
    print("[MAIN] Starting web server on port 8721...")
    web_thread = threading.Thread(daemon=True, target=start_web_server)
    web_thread.start()

    await asyncio.gather(
        sync_task(config, plex),
        update_posters_task(config, plex),
        *[poster_worker(i, config, plex) for i in range(POSTER_WORKERS)]
    )


def start_web_server():
    """Start Flask web server in separate thread."""
    try:
        from googlarr.web import app
        app.run(host='0.0.0.0', port=8721, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[WEB] Error starting web server: {e}")


if __name__ == "__main__":
    asyncio.run(main())

