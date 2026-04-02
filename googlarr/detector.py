"""
Face and eye detection module using MediaPipe and OpenCV.
"""
from typing import List, Tuple, Dict
import logging
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as tasks_python
from mediapipe.tasks.python import vision as tasks_vision
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Full 16-point eye contour indices for the 478-point MediaPipe face mesh.
# Averaging all contour points gives a much more accurate centre and size
# than the original code which only used the two corner landmarks (33/133, 362/263).
LEFT_EYE_CONTOUR  = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]


@dataclass
class EyeLocation:
    left: Tuple[int, int]
    right: Tuple[int, int]
    left_size: Tuple[int, int]
    right_size: Tuple[int, int]
    face_size: Tuple[int, int]
    face_center: Tuple[int, int]
    confidence: float = 1.0
    rotation: float = 0.0


class FaceDetector:
    """Face and eye detection using MediaPipe with OpenCV Haar fallback."""

    def __init__(self, config):
        face_detector_options = tasks_vision.FaceDetectorOptions(
            base_options=tasks_python.BaseOptions(model_asset_path='assets/face_detector.tflite'),
            min_detection_confidence=config['face_detection_confidence'],
        )
        self.face_detection = tasks_vision.FaceDetector.create_from_options(face_detector_options)

        face_landmarker_options = tasks_vision.FaceLandmarkerOptions(
            base_options=tasks_python.BaseOptions(model_asset_path='assets/face_landmarker.task'),
            num_faces=config['max_faces'],
            min_face_detection_confidence=config['landmark_detection_confidence'],
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.face_mesh = tasks_vision.FaceLandmarker.create_from_options(face_landmarker_options)

        if config['use_haar_fallback']:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            self.profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_profileface.xml'
            )

    def _rotation(self, left: Tuple[int, int], right: Tuple[int, int]) -> float:
        return float(np.arctan2(right[1] - left[1], right[0] - left[0]) * 180 / np.pi)

    def _eye_stats(self, pts):
        """Return (centre_x, centre_y, width, height) for a set of (x,y) points."""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (
            int(sum(xs) / len(xs)),
            int(sum(ys) / len(ys)),
            int(max(xs) - min(xs)),
            int(max(ys) - min(ys)),
        )

    def detect_faces_mediapipe(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        orig_h, orig_w = image_rgb.shape[:2]

        # Downscale large images for detection.
        # IMPORTANT: track the scale so we can map coordinates back to the
        # original resolution — the original code forgot this step.
        det_scale = 1.0
        if orig_h > 2000:
            det_scale = 1500.0 / orig_h
            image_rgb = cv2.resize(image_rgb, (0, 0), fx=det_scale, fy=det_scale)

        det_h, det_w = image_rgb.shape[:2]
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

        # Stage 1: bounding boxes via FaceDetector
        face_result = self.face_detection.detect(mp_image)
        face_boxes  = []
        face_scores = []
        if face_result.detections:
            for det in face_result.detections:
                bb = det.bounding_box
                fx = max(0, bb.origin_x)
                fy = max(0, bb.origin_y)
                fw = min(bb.width,  det_w - fx)
                fh = min(bb.height, det_h - fy)
                if fw > 0 and fh > 0:
                    face_boxes.append((fx, fy, fw, fh))
                    score = det.categories[0].score if det.categories else 1.0
                    face_scores.append(score)

        # Stage 2: precise landmarks via FaceLandmarker (full image)
        lm_result = self.face_mesh.detect(mp_image)
        if not lm_result.face_landmarks:
            logger.info("MediaPipe FaceLandmarker: no landmarks found")
            return []

        eye_locations = []

        for face_idx, face_landmarks in enumerate(lm_result.face_landmarks):
            # Convert normalised landmark coords to ORIGINAL image pixel coords.
            # Multiply by detection-image size, then divide by det_scale.
            pts = [
                (lm.x * det_w / det_scale, lm.y * det_h / det_scale)
                for lm in face_landmarks
            ]

            # Eye centres and sizes from full contours (16 points each)
            l_pts = [pts[i] for i in LEFT_EYE_CONTOUR]
            r_pts = [pts[i] for i in RIGHT_EYE_CONTOUR]
            lcx, lcy, lw, lh = self._eye_stats(l_pts)
            rcx, rcy, rw, rh = self._eye_stats(r_pts)
            left_center  = (lcx, lcy)
            right_center = (rcx, rcy)

            # Eye midpoint for matching to face boxes
            mid_x = (lcx + rcx) / 2
            mid_y = (lcy + rcy) / 2

            # Match this landmark set to the closest face box
            best_idx   = -1
            best_score = float('inf')
            for i, (fx, fy, fw, fh) in enumerate(face_boxes):
                # Scale face box coords to original image space for comparison
                fc_x = (fx + fw / 2) / det_scale
                fc_y = (fy + fh / 2) / det_scale
                fw_o = fw / det_scale
                fh_o = fh / det_scale
                dist = np.sqrt((mid_x - fc_x) ** 2 + (mid_y - fc_y) ** 2)
                norm = dist / (fw_o + fh_o)
                threshold = 0.4 if config['movie_poster_mode'] else 0.3
                if norm < threshold and norm < best_score:
                    best_score = norm
                    best_idx   = i

            if best_idx >= 0:
                fx, fy, fw, fh = face_boxes[best_idx]
                face_size   = (int(fw / det_scale), int(fh / det_scale))
                face_center = (int((fx + fw / 2) / det_scale), int((fy + fh / 2) / det_scale))
                confidence  = face_scores[best_idx]
                face_boxes.pop(best_idx)
                face_scores.pop(best_idx)
            else:
                if not config['movie_poster_mode']:
                    logger.warning(f"No matching face box for landmark set {face_idx}, skipping")
                    continue
                # Derive face bounding box from all landmarks
                all_x = [p[0] for p in pts]
                all_y = [p[1] for p in pts]
                face_size   = (int(max(all_x) - min(all_x)), int(max(all_y) - min(all_y)))
                face_center = (int((min(all_x) + max(all_x)) / 2), int((min(all_y) + max(all_y)) / 2))
                confidence  = 0.6

            eye_locations.append(EyeLocation(
                left=left_center,
                right=right_center,
                left_size=(max(lw, 10), max(lh, 6)),
                right_size=(max(rw, 10), max(rh, 6)),
                face_size=face_size,
                face_center=face_center,
                confidence=confidence,
                rotation=self._rotation(left_center, right_center),
            ))

        eye_locations.sort(key=lambda x: x.confidence, reverse=True)
        logger.info(f"MediaPipe: {len(eye_locations)} face(s) detected")
        return eye_locations

    def detect_faces_opencv(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        """Haar cascade fallback."""
        gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = list(self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(30, 30)))

        if config['movie_poster_mode'] and len(faces) < 2:
            profile = list(self.profile_cascade.detectMultiScale(gray, 1.2, 5, minSize=(30, 30)))
            flipped = cv2.flip(gray, 1)
            w_img   = gray.shape[1]
            for (x, y, w, h) in self.profile_cascade.detectMultiScale(flipped, 1.2, 5, minSize=(30, 30)):
                profile.append((w_img - x - w, y, w, h))
            faces.extend(profile)

        eye_locations = []
        for (x, y, w, h) in faces:
            roi  = gray[y:y+h, x:x+w]
            if roi.size == 0:
                continue
            eyes = sorted(
                self.eye_cascade.detectMultiScale(roi, 1.2, 5, minSize=(7, 7)),
                key=lambda e: e[0],
            )

            if len(eyes) >= 2:
                le, re       = eyes[0], eyes[1]
                left_center  = (x + le[0] + le[2]//2, y + le[1] + le[3]//2)
                right_center = (x + re[0] + re[2]//2, y + re[1] + re[3]//2)
                left_size    = (max(le[2], 10), max(le[3], 6))
                right_size   = (max(re[2], 10), max(re[3], 6))
            elif config['movie_poster_mode'] and len(eyes) == 1:
                e      = eyes[0]
                ecx    = x + e[0] + e[2]//2
                ecy    = y + e[1] + e[3]//2
                offset = int(w * 0.4)
                if e[0] < w / 2:
                    left_center, right_center = (ecx, ecy), (ecx + offset, ecy)
                else:
                    left_center, right_center = (ecx - offset, ecy), (ecx, ecy)
                left_size = right_size = (max(e[2], 10), max(e[3], 6))
            else:
                continue

            eye_locations.append(EyeLocation(
                left=left_center,
                right=right_center,
                left_size=left_size,
                right_size=right_size,
                face_size=(w, h),
                face_center=(x + w//2, y + h//2),
                confidence=0.65,
                rotation=self._rotation(left_center, right_center),
            ))

        logger.info(f"OpenCV: {len(eye_locations)} face(s) detected")
        return eye_locations

    def detect_eyes(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        eye_locations = self.detect_faces_mediapipe(image, config)

        if not eye_locations and config['use_haar_fallback']:
            logger.info("Falling back to OpenCV Haar cascades")
            eye_locations = self.detect_faces_opencv(image, config)

        if not eye_locations and config['movie_poster_mode']:
            logger.info("Retrying with histogram equalisation")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            eq   = cv2.cvtColor(cv2.equalizeHist(gray), cv2.COLOR_GRAY2BGR)
            eye_locations = self.detect_faces_mediapipe(eq, config)
            if not eye_locations:
                eye_locations = self.detect_faces_opencv(eq, config)

        return eye_locations
