import os
import requests
from plexapi.server import PlexServer


class PlexAdapter:
    def __init__(self, config: dict):
        self._plex = PlexServer(config['server']['url'], config['server']['token'])

    def get_library_items(self, library_name: str) -> list[dict]:
        library = self._plex.library.section(library_name)
        items = []
        for item in library.all():
            items.append({
                'item_id': str(item.ratingKey),
                'title': item.title,
                'has_seasons': item.TYPE == 'show',
            })
        return items

    def get_seasons(self, item_id: str) -> list[dict]:
        item = self._plex.fetchItem(int(item_id))
        seasons = []
        for season in item.seasons():
            if season.thumb:
                seasons.append({
                    'item_id': str(season.ratingKey),
                    'title': season.title,
                })
        return seasons

    def download_poster(self, item_id: str, save_path: str) -> None:
        item = self._plex.fetchItem(int(item_id))
        url = item.thumbUrl
        response = requests.get(url, headers={'Accept': 'image/jpeg'}, stream=True)
        response.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

    def upload_poster(self, item_id: str, image_path: str) -> None:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Poster image not found: {image_path}")
        item = self._plex.fetchItem(int(item_id))
        item.uploadPoster(filepath=str(image_path))
