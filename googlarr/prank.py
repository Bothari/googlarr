import os
import cv2
from googlarr.detector import FaceDetector
from googlarr.overlay import process_image
from googlarr.db import get_items_for_update, update_item_status

overlay_img = None
face_detector = None


def initialize_detector_and_overlay(config):
    global face_detector, overlay_img
    face_detector = FaceDetector(config)
    overlay_img = cv2.imread("assets/eye.png", cv2.IMREAD_UNCHANGED)


def generate_prank_poster(original_path, prank_path, config):

    global face_detector, overlay_img

    img_bgr = cv2.imread(original_path)
    if img_bgr is None:
        print(f"[PRANK] Failed to read image: {original_path}")
        raise ValueError(f"Failed to read image: {original_path}")

    eye_locations = face_detector.detect_eyes(img_bgr, config['detection'])
    if not eye_locations:
        print(f"[PRANK] No eyes detected: {original_path}")
        raise ValueError(f"No eyes detected in: {original_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

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

    prank_img_bgr = cv2.cvtColor(prank_img_rgb, cv2.COLOR_RGB2BGR)
    os.makedirs(os.path.dirname(prank_path), exist_ok=True)
    cv2.imwrite(prank_path, prank_img_bgr)
    print(f"[PRANK] Wrote prankified poster to {prank_path}")


def apply_pranks(config, server) -> int:
    """Apply prank posters to all PRANK_GENERATED items. Returns count applied."""
    items = get_items_for_update(config['database'])
    count = 0
    for item in items:
        if item['status'] == 'PRANK_GENERATED':
            try:
                server.upload_poster(item['item_id'], item['prank_path'])
                update_item_status(config['database'], item['item_id'], 'PRANK_APPLIED')
                print(f"[APPLY] Applied prank poster to {item['title']}")
                count += 1
            except Exception as e:
                update_item_status(config['database'], item['item_id'], 'FAILED')
                print(f"[APPLY] Error applying prank to {item['title']}: {e}")
    return count


def restore_originals(config, server) -> int:
    """Restore original posters for all PRANK_APPLIED items. Returns count restored."""
    items = get_items_for_update(config['database'])
    count = 0
    for item in items:
        if item['status'] == 'PRANK_APPLIED':
            try:
                server.upload_poster(item['item_id'], item['original_path'])
                update_item_status(config['database'], item['item_id'], 'PRANK_GENERATED')
                print(f"[RESTORE] Restored original poster for {item['title']}")
                count += 1
            except Exception as e:
                update_item_status(config['database'], item['item_id'], 'FAILED')
                print(f"[RESTORE] Error restoring original for {item['title']}: {e}")
    return count
