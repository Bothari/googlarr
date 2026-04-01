import base64
import os
import requests


class EmbyAdapter:
    def __init__(self, config: dict):
        self._base_url = config['server']['url'].rstrip('/')
        self._token = config['server']['token']
        self._headers = {'X-Emby-Token': self._token}

        resp = requests.get(f"{self._base_url}/Users/Me", headers=self._headers)
        if resp.ok:
            self._user_id = resp.json()['Id']
        else:
            # Some Emby versions return 500 for /Users/Me with API keys; fall back to /Users
            resp = requests.get(f"{self._base_url}/Users", headers=self._headers)
            resp.raise_for_status()
            users = resp.json()
            admin = next((u for u in users if u.get('Policy', {}).get('IsAdministrator')), users[0])
            self._user_id = admin['Id']

    def _get_library_id(self, library_name: str) -> str:
        resp = requests.get(f"{self._base_url}/Library/VirtualFolders", headers=self._headers)
        resp.raise_for_status()
        for folder in resp.json():
            if folder['Name'] == library_name:
                return folder['ItemId']
        raise ValueError(f"Library not found: {library_name}")

    def get_library_items(self, library_name: str) -> list[dict]:
        library_id = self._get_library_id(library_name)
        resp = requests.get(
            f"{self._base_url}/Users/{self._user_id}/Items",
            headers=self._headers,
            params={
                'ParentId': library_id,
                'Recursive': 'true',
                'IncludeItemTypes': 'Movie,Series',
            }
        )
        resp.raise_for_status()
        items = []
        for item in resp.json().get('Items', []):
            items.append({
                'item_id': item['Id'],
                'title': item['Name'],
                'has_seasons': item['Type'] == 'Series',
            })
        return items

    def get_seasons(self, item_id: str) -> list[dict]:
        resp = requests.get(
            f"{self._base_url}/Shows/{item_id}/Seasons",
            headers=self._headers,
            params={'UserId': self._user_id}
        )
        resp.raise_for_status()
        seasons = []
        for season in resp.json().get('Items', []):
            if season.get('ImageTags', {}).get('Primary'):
                seasons.append({
                    'item_id': season['Id'],
                    'title': season['Name'],
                })
        return seasons

    def download_poster(self, item_id: str, save_path: str) -> None:
        resp = requests.get(
            f"{self._base_url}/Items/{item_id}/Images/Primary",
            headers=self._headers,
            stream=True
        )
        resp.raise_for_status()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            for chunk in resp.iter_content(1024):
                f.write(chunk)

    def upload_poster(self, item_id: str, image_path: str) -> None:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Poster image not found: {image_path}")
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        resp = requests.post(
            f"{self._base_url}/Items/{item_id}/Images/Primary",
            headers={**self._headers, 'Content-Type': 'image/jpeg'},
            data=image_data
        )
        resp.raise_for_status()
