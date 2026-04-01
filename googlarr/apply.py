from googlarr.server import create_server
from googlarr.config import load_config
from googlarr.prank import apply_pranks, initialize_detector_and_overlay


def main():
    config = load_config()
    initialize_detector_and_overlay(config['detection'])
    server = create_server(config)

    count = apply_pranks(config, server)
    print(f"\nApplied {count} prank poster(s)")


if __name__ == "__main__":
    main()
