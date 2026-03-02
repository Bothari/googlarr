import sys
import sqlite3
from collections import Counter
from datetime import datetime
from croniter import croniter
from googlarr.config import load_config

def print_schedule_info(config):
    """Print next apply/restore times."""
    now = datetime.now()
    cron_on = croniter(config['schedule']['start'], now)
    cron_off = croniter(config['schedule']['stop'], now)

    next_on = cron_on.get_next(datetime)
    next_off = cron_off.get_next(datetime)

    print("Schedule Information:")
    print(f"  Next apply:    {next_on}")
    print(f"  Next restore:  {next_off}")
    print()

def print_summary(db_path, config=None):
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT status FROM library_items")
        rows = c.fetchall()

    if not rows:
        print("No items found in the database.")
        return

    counts = Counter(status for (status,) in rows)

    print("Database Status Summary:\n")
    for status, count in sorted(counts.items()):
        print(f"  {status:20} {count}")

    print(f"\n  Total items: {sum(counts.values())}")
    print()

    # Print schedule info if config is available
    if config:
        print_schedule_info(config)

    # Print FAILED items if any
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT item_id, title, retry_count FROM library_items WHERE status = 'FAILED' ORDER BY retry_count DESC LIMIT 10")
        failed_items = [dict(row) for row in c.fetchall()]

    if failed_items:
        print("Failed Items (up to 10):")
        for item in failed_items:
            print(f"  {item['title']:40} (ID: {item['item_id']}, retries: {item['retry_count']}/3)")
        print()

def print_item_status(db_path, item_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT item_id, title, status, retry_count FROM library_items WHERE item_id = ?",
            (item_id,)
        )
        row = c.fetchone()

    if not row:
        print(f"No item found with ID {item_id}")
        return

    item = dict(row)
    print(f"Item ID:        {item['item_id']}")
    print(f"Title:          {item['title']}")
    print(f"Status:         {item['status']}")
    print(f"Retry Count:    {item['retry_count']}/3")

def main():
    config = load_config()
    db_path = config['database']

    if len(sys.argv) == 2:
        item_id = sys.argv[1]
        print_item_status(db_path, item_id)
    else:
        print_summary(db_path, config)

if __name__ == "__main__":
    main()


