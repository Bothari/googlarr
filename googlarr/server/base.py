from typing import Protocol


class MediaServer(Protocol):
    def get_library_items(self, library_name: str) -> list[dict]:
        """Return list of {item_id: str, title: str, has_seasons: bool}."""
        ...

    def get_seasons(self, item_id: str) -> list[dict]:
        """Return list of {item_id: str, title: str} for seasons that have a poster."""
        ...

    def download_poster(self, item_id: str, save_path: str) -> None:
        """Download the primary poster for item_id and save to save_path."""
        ...

    def upload_poster(self, item_id: str, image_path: str) -> None:
        """Upload the image at image_path as the primary poster for item_id."""
        ...
