import os
import cv2
import requests
from googlarr.detector import FaceDetector
from googlarr.overlay import process_image
from googlarr.db import get_items_for_update, update_item_status

overlay_img = None
face_detector = None


def initialize_detector_and_overlay(config):
    global face_detector, overlay_img
    face_detector = FaceDetector(config)
    overlay_img = cv2.imread("assets/eye.png", cv2.IMREAD_UNCHANGED)


def download_poster(plex, item, save_path, config):
    plex_item = plex.fetchItem(int(item['item_id']))
    url = plex_item.thumbUrl
    headers = {'Accept': 'image/jpeg'}
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code == 200:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)  # Ensure directory exists
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

def generate_prank_poster(original_path, prank_path, config):

    global face_detector, overlay_img

    img_bgr = cv2.imread(original_path)
    if img_bgr is None:
        print(f"[PRANK] Failed to read image: {original_path}")
        raise ValueError(f"Failed to read image: {original_path}")

    # Detect eyes using face detector
    eye_locations = face_detector.detect_eyes(img_bgr, config['detection'])
    if not eye_locations:
        print(f"[PRANK] No eyes detected: {original_path}")
        raise ValueError(f"No eyes detected in: {original_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Apply googly eyes
    try:
        prank_img_rgb = process_image(
            base_image=img_rgb,
            overlay_image=overlay_img,
            eye_locations=eye_locations,
            config=config['detection']
        )
    except Exception as e:
        print(f"[PRANK] Error applying googly eyes: {e}")
        raise

    # Convert and save
    prank_img_bgr = cv2.cvtColor(prank_img_rgb, cv2.COLOR_RGB2BGR)
    os.makedirs(os.path.dirname(prank_path), exist_ok=True)
    cv2.imwrite(prank_path, prank_img_bgr)
    print(f"[PRANK] Wrote prankified poster to {prank_path}")


def set_poster(plex_item, image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Poster image not found: {image_path}")

    plex_item.uploadPoster(filepath=str(image_path))


def apply_pranks(config, plex) -> int:
    """Apply prank posters to all PRANK_GENERATED items. Returns count applied."""
    items = get_items_for_update(config['database'])
    count = 0
    for item in items:
        if item['status'] == 'PRANK_GENERATED':
            try:
                plex_item = plex.fetchItem(int(item['item_id']))
                set_poster(plex_item, item['prank_path'])
                update_item_status(config['database'], item['item_id'], 'PRANK_APPLIED')
                print(f"[APPLY] Applied prank poster to {item['title']}")
                count += 1
            except Exception as e:
                update_item_status(config['database'], item['item_id'], 'FAILED')
                print(f"[APPLY] Error applying prank to {item['title']}: {e}")
    return count


def restore_originals(config, plex) -> int:
    """Restore original posters for all PRANK_APPLIED items. Returns count restored."""
    items = get_items_for_update(config['database'])
    count = 0
    for item in items:
        if item['status'] == 'PRANK_APPLIED':
            try:
                plex_item = plex.fetchItem(int(item['item_id']))
                set_poster(plex_item, item['original_path'])
                update_item_status(config['database'], item['item_id'], 'PRANK_GENERATED')
                print(f"[RESTORE] Restored original poster for {item['title']}")
                count += 1
            except Exception as e:
                update_item_status(config['database'], item['item_id'], 'FAILED')
                print(f"[RESTORE] Error restoring original for {item['title']}: {e}")
    return count

