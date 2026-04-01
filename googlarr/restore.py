from googlarr.server import create_server
from googlarr.config import load_config
from googlarr.prank import restore_originals, initialize_detector_and_overlay


def main():
    config = load_config()
    initialize_detector_and_overlay(config['detection'])
    server = create_server(config)

    count = restore_originals(config, server)
    print(f"\nRestored {count} original poster(s)")


if __name__ == "__main__":
    main()
