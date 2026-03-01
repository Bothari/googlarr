import traceback
import asyncio
import os
import time
from datetime import datetime, timedelta
from croniter import croniter

from plexapi.server import PlexServer
from googlarr.config import load_config
from googlarr.db import (
    init_db,
    sync_library_with_plex,
    claim_next_poster_task,
    update_item_status,
    get_items_for_update,
    reset_working_tasks
)
from googlarr.prank import download_poster, generate_prank_poster, set_poster, initialize_detector_and_overlay

# --- CONFIG ---
SYNC_INTERVAL_MINUTES = 360
POSTER_WORKERS = 1
WORKER_IDLE_SLEEP_SECONDS = 30


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
        print("[SYNC] Syncing library with Plex...")
        sync_library_with_plex(config, plex)
        await asyncio.sleep(SYNC_INTERVAL_MINUTES * 60)


async def poster_worker(worker_id, config, plex):
    while True:
        item = claim_next_poster_task(config['database'])

        if not item:
            print(f"[POSTER-{worker_id}] Sleeping...")
            await asyncio.sleep(WORKER_IDLE_SLEEP_SECONDS)
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
        items = get_items_for_update(config['database'])
        for item in items:
            if item['status'] == 'PRANK_GENERATED':
                try:
                    plex_item = plex.fetchItem(int(item['item_id']))
                    set_poster(plex_item, item['prank_path'])
                    update_item_status(config['database'], item['item_id'], 'PRANK_APPLIED')
                    print(f"[UPDATE] Applied prank poster to {item['title']} (startup)")
                except Exception as e:
                    update_item_status(config['database'], item['item_id'], 'FAILED')
                    print(f"[UPDATE] Error applying startup prank to {item['title']}: {e}")
    else:
        print("[UPDATE] Restoring any pranked posters from startup...")
        items = get_items_for_update(config['database'])
        for item in items:
            if item['status'] == 'PRANK_APPLIED':
                try:
                    plex_item = plex.fetchItem(int(item['item_id']))
                    set_poster(plex_item, item['original_path'])
                    update_item_status(config['database'], item['item_id'], 'PRANK_GENERATED')
                    print(f"[UPDATE] Restored original poster for {item['title']} (startup)")
                except Exception as e:
                    update_item_status(config['database'], item['item_id'], 'FAILED')
                    print(f"[UPDATE] Error restoring startup poster for {item['title']}: {e}")

    while True:
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
        print(f"[UPDATE] Next action: {action.upper()} at {next_event}. Current time: {now}. Sleeping for {sleep_duration:.0f} seconds...")
        await asyncio.sleep(sleep_duration)

        # Do the update
        items = get_items_for_update(config['database'])
        for item in items:
            plex_item = plex.fetchItem(int(item['item_id']))

            try:
                if action == "apply" and item['status'] == 'PRANK_GENERATED':
                    set_poster(plex_item, item['prank_path'])
                    update_item_status(config['database'], item['item_id'], 'PRANK_APPLIED')
                    print(f"[UPDATE] Applied prank poster to {item['title']}")

                elif action == "restore" and item['status'] == 'PRANK_APPLIED':
                    set_poster(plex_item, item['original_path'])
                    update_item_status(config['database'], item['item_id'], 'PRANK_GENERATED')
                    print(f"[UPDATE] Restored original poster for {item['title']}")

            except Exception as e:
                update_item_status(config['database'], item['item_id'], 'FAILED')
                print(f"[UPDATE] Error updating poster for {item['title']}: {e}")



async def main():
    config = load_config()
    init_db(config['database'])
    reset_working_tasks(config['database'])
    initialize_detector_and_overlay(config['detection'])
    plex = PlexServer(config['plex']['url'], config['plex']['token'])

    await asyncio.gather(
        sync_task(config, plex),
        update_posters_task(config, plex),
        *[poster_worker(i, config, plex) for i in range(POSTER_WORKERS)]
    )


if __name__ == "__main__":
    asyncio.run(main())

