from plexapi.server import PlexServer
from googlarr.config import load_config
from googlarr.prank import restore_originals, initialize_detector_and_overlay


def main():
    config = load_config()
    initialize_detector_and_overlay(config['detection'])
    plex = PlexServer(config['plex']['url'], config['plex']['token'])

    count = restore_originals(config, plex)
    print(f"\nRestored {count} original poster(s)")


if __name__ == "__main__":
    main()
