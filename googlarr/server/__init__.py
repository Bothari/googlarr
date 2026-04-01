from googlarr.server.base import MediaServer
from googlarr.server.plex import PlexAdapter
from googlarr.server.emby import EmbyAdapter


def create_server(config: dict) -> MediaServer:
    server_type = config['server']['type']
    if server_type == 'plex':
        return PlexAdapter(config)
    elif server_type in ('emby', 'jellyfin'):
        return EmbyAdapter(config)
    else:
        raise ValueError(f"Unknown server type: {server_type!r}. Must be one of: plex, emby, jellyfin")


__all__ = ['MediaServer', 'create_server']
