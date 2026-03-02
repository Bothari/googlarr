import sqlite3
from pathlib import Path


def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS library_items (
                item_id TEXT PRIMARY KEY,
                title TEXT,
                library TEXT,
                original_path TEXT,
                prank_path TEXT,
                status TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()

        # Add retry_count column if it doesn't exist (for existing databases)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(library_items)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'retry_count' not in columns:
            conn.execute("ALTER TABLE library_items ADD COLUMN retry_count INTEGER DEFAULT 0")
            conn.commit()


def reset_working_tasks(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE library_items SET status = 'NEW' WHERE status = 'WORKING_DOWNLOAD'")
        conn.execute("UPDATE library_items SET status = 'ORIGINAL_DOWNLOADED' WHERE status = 'WORKING_PRANKIFY'")
        conn.commit()


def sync_library_with_plex(config, plex):

    originals_dir = config['paths']['originals_dir']
    prank_dir = config['paths']['prank_dir']

    for lib_name in config['plex']['libraries']:
        print(f"[SYNC] Syncing library: {lib_name}")
        library = plex.library.section(lib_name)

        with sqlite3.connect(config['database']) as conn:
            c = conn.cursor()

            current_ids = set()
            for item in library.all():
                item_id = str(item.ratingKey)
                title = item.title

                print(f"[SYNC] Adding item: {item_id}, {title}, {originals_dir}/{item_id}.jpg, {prank_dir}/{item_id}.jpg")

                current_ids.add(item_id)

                c.execute(
                    "INSERT OR IGNORE INTO library_items (item_id, title, library, original_path, prank_path, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item_id,
                        title,
                        lib_name,
                        f"{originals_dir}/{item_id}.jpg",
                        f"{prank_dir}/{item_id}.jpg",
                        'NEW'
                    )
                )

                if hasattr(item, 'seasons'):
                    for season in item.seasons():

                        season_id = str(season.ratingKey)
                        season_title = f"{item.title} - {season.title}"

                        if not season.thumb:
                            print(f"[SYNC] Skipping {season_title}: No poster")
                            continue

                        print(f"[SYNC] Adding season: {season_id}, {season_title}, {originals_dir}/{season_id}.jpg, {prank_dir}/{season_id}.jpg")

                        c.execute(
                            "INSERT OR IGNORE INTO library_items (item_id, title, library, original_path, prank_path, status) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                season_id,
                                season_title,
                                lib_name,
                                f"{originals_dir}/{season_id}.jpg",
                                f"{prank_dir}/{season_id}.jpg",
                                'NEW'
                            )
                        )

            conn.commit()


def claim_next_poster_task(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Try to claim a NEW item for downloading
        c.execute("""
            UPDATE library_items
            SET status = 'WORKING_DOWNLOAD'
            WHERE item_id = (
                SELECT item_id FROM library_items
                WHERE status = 'NEW'
                LIMIT 1
            )
            RETURNING *
        """)
        row = c.fetchone()
        if row:
            return dict(row)

        # Try to claim an ORIGINAL_DOWNLOADED item for prankifying
        c.execute("""
            UPDATE library_items
            SET status = 'WORKING_PRANKIFY'
            WHERE item_id = (
                SELECT item_id FROM library_items
                WHERE status = 'ORIGINAL_DOWNLOADED'
                LIMIT 1
            )
            RETURNING *
        """)
        row = c.fetchone()
        if row:
            return dict(row)

        # Try to claim a FAILED item for retry (max 3 retries)
        c.execute("""
            UPDATE library_items
            SET status = 'NEW', retry_count = retry_count + 1
            WHERE item_id = (
                SELECT item_id FROM library_items
                WHERE status = 'FAILED' AND retry_count < 3
                LIMIT 1
            )
            RETURNING *
        """)
        row = c.fetchone()
        return dict(row) if row else None


def update_item_status(db_path, item_id, new_status):
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        if new_status == 'FAILED':
            c.execute("UPDATE library_items SET status = ?, retry_count = retry_count + 1 WHERE item_id = ?", (new_status, item_id))
        else:
            c.execute("UPDATE library_items SET status = ? WHERE item_id = ?", (new_status, item_id))
        conn.commit()


def get_items_for_update(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM library_items WHERE status IN ('PRANK_GENERATED', 'PRANK_APPLIED')")
        return [dict(row) for row in c.fetchall()]


def reset_failed_items(db_path, item_id=None):
    """Reset FAILED items back to NEW with retry_count = 0.

    If item_id is None, reset all FAILED items.
    If item_id is provided, reset only that specific item.

    Returns the count of items reset.
    """
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        if item_id is None:
            # Reset all FAILED items
            c.execute("UPDATE library_items SET status = 'NEW', retry_count = 0 WHERE status = 'FAILED'")
        else:
            # Reset specific item if it's FAILED
            c.execute("UPDATE library_items SET status = 'NEW', retry_count = 0 WHERE item_id = ? AND status = 'FAILED'", (item_id,))

        conn.commit()
        return c.rowcount

