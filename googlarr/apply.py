from plexapi.server import PlexServer
from googlarr.config import load_config
from googlarr.prank import apply_pranks, initialize_detector_and_overlay


def main():
    config = load_config()
    initialize_detector_and_overlay(config['detection'])
    plex = PlexServer(config['plex']['url'], config['plex']['token'])

    count = apply_pranks(config, plex)
    print(f"\nApplied {count} prank poster(s)")


if __name__ == "__main__":
    main()
