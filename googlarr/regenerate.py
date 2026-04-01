import sys
import traceback
import os
from googlarr.server import create_server
from googlarr.config import load_config
from googlarr.prank import (
    initialize_detector_and_overlay,
    generate_prank_poster,
)
from googlarr.db import update_item_status

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m googlarr.regenerate <item_id>")
        sys.exit(1)

    item_id = sys.argv[1]
    config = load_config()
    initialize_detector_and_overlay(config['detection'])
    server = create_server(config)

    original_path = f"{config['paths']['originals_dir']}/{item_id}.jpg"
    prank_path = f"{config['paths']['prank_dir']}/{item_id}.jpg"

    try:
        # Download original if missing
        if not os.path.exists(original_path):
            print(f"Downloading original poster for item {item_id}...")
            server.download_poster(item_id, original_path)
            update_item_status(config['database'], item_id, 'ORIGINAL_DOWNLOADED')

        # Regenerate prank
        print(f"Generating prank poster for item {item_id}...")
        generate_prank_poster(original_path, prank_path, config)
        update_item_status(config['database'], item_id, 'PRANK_GENERATED')

        print(f"Done. Prank poster saved to {prank_path}")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"Error processing item {item_id}: {e.__class__.__name__}: {e}")
        print(tb)

        update_item_status(config['database'], item_id, 'FAILED')


if __name__ == "__main__":
    main()
