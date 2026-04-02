"""
Face and eye detection module using MediaPipe and OpenCV.
"""
from typing import List, Tuple, Optional, Dict
import logging
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as tasks_python
from mediapipe.tasks.python import vision as tasks_vision
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EyeLocation:
    """Data class to store eye location information."""
    left: Tuple[int, int]  # (x, y) center coordinates
    right: Tuple[int, int]
    left_size: Tuple[int, int]  # (width, height)
    right_size: Tuple[int, int]
    face_size: Tuple[int, int]  # (width, height) of the face
    face_center: Tuple[int, int]  # (x, y) center of the face
    confidence: float = 1.0  # Detection confidence score
    rotation: float = 0.0  # Face rotation in degrees

class FaceDetector:
    """Face and eye detection using MediaPipe with OpenCV fallback."""
    
    def __init__(self, config):
        """Initialize the face detector with MediaPipe and OpenCV cascades."""
        # Initialize MediaPipe Face Detector (tasks API)
        face_detector_options = tasks_vision.FaceDetectorOptions(
            base_options=tasks_python.BaseOptions(model_asset_path='assets/face_detector.tflite'),
            min_detection_confidence=config['face_detection_confidence']
        )
        self.face_detection = tasks_vision.FaceDetector.create_from_options(face_detector_options)

        # Initialize MediaPipe Face Landmarker (tasks API)
        face_landmarker_options = tasks_vision.FaceLandmarkerOptions(
            base_options=tasks_python.BaseOptions(model_asset_path='assets/face_landmarker.task'),
            num_faces=config['max_faces'],
            min_face_detection_confidence=config['landmark_detection_confidence'],
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False
        )
        self.face_mesh = tasks_vision.FaceLandmarker.create_from_options(face_landmarker_options)
        
        # Initialize OpenCV Haar cascades as fallback
        if config['use_haar_fallback']:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
            # Add additional cascade for profile faces
            self.profile_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_profileface.xml'
            )

    def _calculate_face_rotation(self, left_eye: Tuple[int, int], right_eye: Tuple[int, int]) -> float:
        """
        Calculate face rotation angle in degrees based on eye positions.
        
        Args:
            left_eye: (x,y) coordinates of left eye
            right_eye: (x,y) coordinates of right eye
            
        Returns:
            Rotation angle in degrees
        """
        dx = right_eye[0] - left_eye[0]
        dy = right_eye[1] - left_eye[1]
        
        # Calculate angle in radians and convert to degrees
        angle = np.arctan2(dy, dx) * 180 / np.pi
        
        return angle

    def detect_faces_mediapipe(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        """
        Detect faces and eyes using MediaPipe.

        Args:
            image: numpy.ndarray in BGR format

        Returns:
            List[EyeLocation]: List of detected eye locations
        """
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if image_rgb.shape[0] > 2000:
            scale = 1500 / image_rgb.shape[0]
            image_rgb = cv2.resize(image_rgb, (0, 0), fx=scale, fy=scale)

        height, width = image_rgb.shape[:2]

        # Wrap image for mediapipe tasks API
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

        # First use FaceDetection to get face bounding boxes
        face_detection_result = self.face_detection.detect(mp_image)
        face_boxes = []
        face_scores = []

        if face_detection_result.detections:
            for detection in face_detection_result.detections:
                bbox = detection.bounding_box
                face_x = max(0, bbox.origin_x)
                face_y = max(0, bbox.origin_y)
                face_w = min(bbox.width, width - face_x)
                face_h = min(bbox.height, height - face_y)

                if face_w > 0 and face_h > 0:
                    face_boxes.append((face_x, face_y, face_w, face_h))
                    score = detection.categories[0].score if detection.categories else 1.0
                    face_scores.append(score)
                    logger.info(f"Face detected with dimensions: {face_w}x{face_h}, confidence: {score:.2f}")

        # Then use FaceLandmarker for precise eye landmarks
        landmark_result = self.face_mesh.detect(mp_image)
        if not landmark_result.face_landmarks:
            logger.info("MediaPipe detection failed: no face landmarks")
            return []

        eye_locations = []

        # Process each face
        for face_index, face_landmarks in enumerate(landmark_result.face_landmarks):
            # MediaPipe face mesh indices for precise eye landmarks
            # Using more accurate inner and outer corners for movie poster faces
            left_eye_indices = [33, 133]   # Left eye corners (inner, outer)
            right_eye_indices = [362, 263] # Right eye corners (inner, outer)
            
            # Get eye coordinates
            left_eye = [(int(face_landmarks[idx].x * width),
                        int(face_landmarks[idx].y * height))
                       for idx in left_eye_indices]
            right_eye = [(int(face_landmarks[idx].x * width),
                         int(face_landmarks[idx].y * height))
                        for idx in right_eye_indices]
            
            # Calculate eye centers and sizes
            left_center = (
                (left_eye[0][0] + left_eye[1][0]) // 2,
                (left_eye[0][1] + left_eye[1][1]) // 2
            )
            right_center = (
                (right_eye[0][0] + right_eye[1][0]) // 2,
                (right_eye[0][1] + right_eye[1][1]) // 2
            )
            
            left_size = (
                max(abs(left_eye[1][0] - left_eye[0][0]), 10),  # Min width of 10px
                max(abs(left_eye[1][1] - left_eye[0][1]), 8)    # Min height of 8px
            )
            right_size = (
                max(abs(right_eye[1][0] - right_eye[0][0]), 10),
                max(abs(right_eye[1][1] - right_eye[0][1]), 8)
            )
            
            # Calculate eye midpoint (center of eyes)
            eye_midpoint = (
                (left_center[0] + right_center[0]) // 2,
                (left_center[1] + right_center[1]) // 2
            )
            
            # Calculate face rotation based on eye positions
            rotation = self._calculate_face_rotation(left_center, right_center)
            
            # Find the best matching face box for this face mesh
            best_match_idx = -1
            best_match_score = float('inf')
            
            for i, (fx, fy, fw, fh) in enumerate(face_boxes):
                # Calculate face box center
                face_center_x = fx + fw // 2
                face_center_y = fy + fh // 2
                
                # Calculate distance between eye midpoint and face center
                distance = np.sqrt(
                    (eye_midpoint[0] - face_center_x) ** 2 + 
                    (eye_midpoint[1] - face_center_y) ** 2
                )
                
                # Normalize by face size for better comparison
                normalized_distance = distance / (fw + fh)
                
                # Adjust for movie poster faces - allow greater distance
                distance_threshold = 0.4 if config['movie_poster_mode'] else 0.3
                
                # If eye midpoint is within reasonable distance of face center
                if normalized_distance < distance_threshold:
                    if normalized_distance < best_match_score:
                        best_match_score = normalized_distance
                        best_match_idx = i
            
            confidence = 1.0
            
            # If we found a matching face box
            if best_match_idx >= 0:
                face_x, face_y, face_w, face_h = face_boxes[best_match_idx]
                face_size = (face_w, face_h)
                face_center = (face_x + face_w // 2, face_y + face_h // 2)
                confidence = face_scores[best_match_idx]
                
                # Remove the face box so it's not matched again
                face_boxes.pop(best_match_idx)
                face_scores.pop(best_match_idx)
                
                logger.info(f"Matched face mesh {face_index} with face box {best_match_idx}")
            else:
                # For movie posters, be more lenient with floating eyes
                if not config['movie_poster_mode'] and len(eye_locations) < len(face_boxes):
                    logger.warning(f"Skipping face mesh {face_index} - no matching face box")
                    continue
                
                # Estimate face size based on eye positions
                face_width = abs(right_center[0] - left_center[0]) * 3  # Approx 3x the inter-eye distance
                face_height = face_width * 1.4  # Typical face aspect ratio
                face_size = (int(face_width), int(face_height))
                
                # Ensure minimum face size
                face_size = (max(face_size[0], 100), max(face_size[1], 100))
                
                # Estimate face center
                eye_midpoint_y = (left_center[1] + right_center[1]) // 2
                # Eyes are typically in the upper half of the face
                face_center = (eye_midpoint[0], int(eye_midpoint_y + face_height * 0.15))
                
                # For movie posters, increase the confidence of estimated faces
                confidence = 0.6 if config['movie_poster_mode'] else 0.5
                logger.info(f"Using estimated face size for face mesh {face_index}")
            
            eye_locations.append(EyeLocation(
                left=left_center,
                right=right_center,
                left_size=left_size,
                right_size=right_size,
                face_size=face_size,
                face_center=face_center,
                confidence=confidence,
                rotation=rotation
            ))
        
        # Sort by confidence (highest first)
        eye_locations.sort(key=lambda x: x.confidence, reverse=True)
        
        # Only return eye locations up to the number of real face detections 
        # plus safety margin (more lenient for movie posters)
        num_detections = 0
        if face_detection_result.detections is not None:
            num_detections = len(face_detection_result.detections)
            
        max_faces = num_detections * 2 if config['movie_poster_mode'] else num_detections + 1
        max_faces = max(max_faces, 2)  # Always allow at least 2 faces
        
        if len(eye_locations) > max_faces:
            logger.warning(f"Limiting detected faces from {len(eye_locations)} to {max_faces}")
            eye_locations = eye_locations[:max_faces]
            
        return eye_locations

    def detect_faces_opencv(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        """
        Detect faces and eyes using OpenCV Haar cascades (fallback method).

        Args:
            image: numpy.ndarray in BGR format

        Returns:
            List[EyeLocation]: List of detected eye locations
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # For movie posters, also try to detect profile faces
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))

        print(f"Open CV: {len(faces)} faces detected")
        
        if config['movie_poster_mode'] and len(faces) < 2:
            # Try to detect profile faces (both left and right profiles)
            profile_faces = self.profile_cascade.detectMultiScale(gray, 1.2, 5, minSize=(30, 30))
            # Also try the flipped image to detect faces looking the other way
            flipped = cv2.flip(gray, 1)
            flipped_profile_faces = self.profile_cascade.detectMultiScale(flipped, 1.2, 5, minSize=(30, 30))
            
            # Convert flipped coordinates back to original image
            width = gray.shape[1]
            for i, (x, y, w, h) in enumerate(flipped_profile_faces):
                flipped_profile_faces[i] = (width - x - w, y, w, h)
                
            # Combine all detected faces
            all_faces = list(faces)
            all_faces.extend(profile_faces)
            all_faces.extend(flipped_profile_faces)
            faces = np.array(all_faces) if all_faces else faces
        
        eye_locations = []
        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            
            # Ensure ROI is valid
            if roi_gray.size == 0:
                continue
                
            eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.2, 5, minSize=(7, 7))

            print(f"Open CV: {len(eyes)} eyes detected")
            
            if len(eyes) >= 2:
                logger.info("Positioning 2 or more eyes")
                # Sort eyes by x-coordinate to determine left and right
                eyes = sorted(eyes, key=lambda e: e[0])
                left_eye, right_eye = eyes[:2]

                logger.info(f"Left: {left_eye}")
                logger.info(f"Right: {right_eye}")
                logger.info(f"{x}, {y}, {w}, {h}")
                
                # Convert coordinates to global image space
                left_center = (
                    x + left_eye[0] + left_eye[2]//2,
                    y + left_eye[1] + left_eye[3]//2
                )
                right_center = (
                    x + right_eye[0] + right_eye[2]//2,
                    y + right_eye[1] + right_eye[3]//2
                )
                
                face_size = (w, h)
                face_center = (x + w//2, y + h//2)
                
                # Calculate rotation angle
                rotation = self._calculate_face_rotation(left_center, right_center)
                
                eye_locations.append(EyeLocation(
                    left=left_center,
                    right=right_center,
                    left_size=(max(left_eye[2], 10), max(left_eye[3], 8)),
                    right_size=(max(right_eye[2], 10), max(right_eye[3], 8)),
                    face_size=face_size,
                    face_center=face_center,
                    confidence=0.6 if config['movie_poster_mode'] else 0.5,  # Higher confidence for movie posters
                    rotation=rotation
                ))
            # Special case for movie posters: if only one eye is detected, estimate the other
            elif config['movie_poster_mode'] and len(eyes) == 1:
                logger.info("Guessing second eye position")
                eye = eyes[0]
                eye_center_x = x + eye[0] + eye[2]//2
                eye_center_y = y + eye[1] + eye[3]//2
                
                # Estimate other eye position based on face width and position
                # If eye is in left half of face, it's the left eye
                if eye[0] < w/2:
                    left_center = (eye_center_x, eye_center_y)
                    # Estimate right eye
                    right_center = (
                        eye_center_x + int(w * 0.4),  # Approx eye separation
                        eye_center_y
                    )
                else:
                    right_center = (eye_center_x, eye_center_y)
                    # Estimate left eye
                    left_center = (
                        eye_center_x - int(w * 0.4),
                        eye_center_y
                    )
                
                face_size = (w, h)
                face_center = (x + w//2, y + h//2)
                
                # Calculate rotation angle
                rotation = self._calculate_face_rotation(left_center, right_center)
                
                eye_locations.append(EyeLocation(
                    left=left_center,
                    right=right_center,
                    left_size=(max(eye[2], 10), max(eye[3], 8)),
                    right_size=(max(eye[2], 10), max(eye[3], 8)),
                    face_size=face_size,
                    face_center=face_center,
                    confidence=0.5,  # Lower confidence for estimated eye
                    rotation=rotation
                ))
        
        return eye_locations

    def detect_eyes(self, image: np.ndarray, config: Dict) -> List[EyeLocation]:
        """
        Detect eyes in an image using MediaPipe with OpenCV fallback.

        Args:
            image: numpy.ndarray in BGR format

        Returns:
            List[EyeLocation]: List of detected eye locations
        """
        # Try MediaPipe first
        eye_locations = self.detect_faces_mediapipe(image, config)
        
        # Fallback to OpenCV if MediaPipe fails and fallback is enabled
        if not eye_locations and config['use_haar_fallback']:
            logger.info("MediaPipe detection failed, falling back to OpenCV")
            eye_locations = self.detect_faces_opencv(image, config)
            
        # For movie posters, if we still have no eyes, try one more technique
        if not eye_locations and config['movie_poster_mode']:
            logger.info("Trying additional movie poster detection technique")
            # Try with equalizing histogram to improve contrast
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            equalized = cv2.equalizeHist(gray)
            equalized_image = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
            eye_locations = self.detect_faces_mediapipe(equalized_image, config)
            
            if not eye_locations:
                eye_locations = self.detect_faces_opencv(equalized_image, config)
        
        return eye_locations 
