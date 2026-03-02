import sys
from googlarr.config import load_config
from googlarr.db import reset_failed_items


def main():
    config = load_config()
    db_path = config['database']

    if len(sys.argv) == 2:
        # Reset specific item
        item_id = sys.argv[1]
        count = reset_failed_items(db_path, item_id=item_id)
        if count > 0:
            print(f"Reset failed item {item_id} back to NEW")
        else:
            print(f"No failed item found with ID {item_id}")
    else:
        # Reset all failed items
        count = reset_failed_items(db_path)
        if count > 0:
            print(f"Reset {count} failed item(s) back to NEW")
        else:
            print("No failed items to reset")


if __name__ == "__main__":
    main()
