"""Face detection, alignment, and preprocessing for LoRA training"""

import os
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Optional
import insightface
from insightface.app import FaceAnalysis
from app.config.settings import settings


class FacePreprocessor:
    """Preprocess images for LoRA training: detect faces, align, and crop to 512x512"""
    
    def __init__(self):
        """Initialize InsightFace model"""
        self.app = FaceAnalysis(name=settings.FACE_DETECTION_MODEL)
        self.app.prepare(ctx_id=0, det_size=(640, 640))
    
    def detect_and_align_face(
        self, image_path: str
    ) -> Optional[Tuple[np.ndarray, Tuple[float, float], Tuple[float, float, float, float]]]:
        """
        Detect and align face from image

        Returns:
            Tuple of (aligned_face_image, face_center_xy, face_bbox) or None
            face_center_xy: (cx, cy) - face center in aligned image (rotation pivot, stays fixed)
            face_bbox: (x1, y1, x2, y2) - face bbox in original image
        """
        img = cv2.imread(image_path)
        if img is None:
            return None

        faces = self.app.get(img)
        if len(faces) == 0:
            return None

        # Prefer frontal faces (yaw close to 0); fallback to largest
        def frontal_score(f):
            if hasattr(f, 'yaw') and f.yaw is not None:
                return -abs(float(f.yaw))  # Prefer smaller |yaw|
            return (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])  # fallback: area

        face = max(faces, key=frontal_score)

        landmarks = face.landmark_2d_106.astype(np.int32)
        aligned_face = self._align_face(img, landmarks)

        # Face center (eye midpoint) - rotation pivot, same in aligned image
        left_eye = landmarks[38]
        right_eye = landmarks[88]
        cx = (float(left_eye[0]) + float(right_eye[0])) / 2.0
        cy = (float(left_eye[1]) + float(right_eye[1])) / 2.0
        bbox = (float(face.bbox[0]), float(face.bbox[1]), float(face.bbox[2]), float(face.bbox[3]))

        return aligned_face, (cx, cy), bbox
    
    def _align_face(self, img: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """
        Align face using landmarks
        
        Args:
            img: Input image
            landmarks: Face landmarks (106 points)
            
        Returns:
            Aligned face image
        """
        # Use eye landmarks for alignment (points 38, 88 for left eye, 43, 93 for right eye)
        left_eye = landmarks[38]
        right_eye = landmarks[88]
        
        # Calculate angle (Python float for OpenCV compatibility)
        dy = float(right_eye[1] - left_eye[1])
        dx = float(right_eye[0] - left_eye[0])
        angle = float(np.degrees(np.arctan2(dy, dx)))
        
        # Get center point (Python floats for OpenCV getRotationMatrix2D)
        cx = (float(left_eye[0]) + float(right_eye[0])) / 2.0
        cy = (float(left_eye[1]) + float(right_eye[1])) / 2.0
        center = (cx, cy)
        
        # Rotate image
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        aligned = cv2.warpAffine(img, rotation_matrix, (img.shape[1], img.shape[0]))
        
        return aligned
    
    def crop_to_square(
        self,
        img: np.ndarray,
        size: int = 512,
        face_center: Optional[Tuple[float, float]] = None,
        face_bbox: Optional[Tuple[float, float, float, float]] = None,
    ) -> np.ndarray:
        """
        Crop image to square centered on face, resize to target size.
        SadTalker needs frontal face centered in crop - image-center crop fails on vertical photos.

        Args:
            img: Input image (aligned)
            size: Target size (default 512)
            face_center: (cx, cy) - face center to crop around
            face_bbox: (x1,y1,x2,y2) - face bbox for sizing
        """
        h, w = img.shape[:2]

        if face_center is not None and face_bbox is not None:
            cx, cy = face_center
            x1, y1, x2, y2 = face_bbox
            face_w = x2 - x1
            face_h = y2 - y1
            # Crop size: face + generous padding (2.5x) for full head
            crop_side = max(face_w, face_h) * 2.5
            crop_side = min(crop_side, min(h, w))  # fit in image
            crop_side = max(crop_side, 256)
            half = crop_side / 2.0
            start_x = int(max(0, min(cx - half, w - crop_side)))
            start_y = int(max(0, min(cy - half, h - crop_side)))
            start_x = min(start_x, max(0, w - int(crop_side)))
            start_y = min(start_y, max(0, h - int(crop_side)))
            crop_dim = min(int(crop_side), w - start_x, h - start_y)
            if crop_dim <= 0:
                crop_dim = min(h, w)
            cropped = img[
                start_y : start_y + crop_dim,
                start_x : start_x + crop_dim,
            ]
        else:
            # Fallback: center crop
            min_dim = min(h, w)
            start_y = (h - min_dim) // 2
            start_x = (w - min_dim) // 2
            cropped = img[start_y : start_y + min_dim, start_x : start_x + min_dim]

        resized = cv2.resize(cropped, (size, size), interpolation=cv2.INTER_LANCZOS4)
        return resized
    
    def process_image(self, image_path: str, output_path: str) -> bool:
        """
        Process single image: detect face, align, crop around face to 512x512.
        Crops centered on face (not image center) for vertical/portrait photos.
        """
        result = self.detect_and_align_face(image_path)
        if result is None:
            return False

        aligned_face, face_center, face_bbox = result

        # Crop around face center (critical for vertical images)
        cropped = self.crop_to_square(
            aligned_face,
            size=settings.LORA_RESOLUTION,
            face_center=face_center,
            face_bbox=face_bbox,
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, cropped)
        return True
    
    def process_batch(self, image_paths: List[str], user_id: str) -> List[str]:
        """
        Process multiple images for a user
        
        Args:
            image_paths: List of input image paths
            user_id: User ID for organizing output
            
        Returns:
            List of processed image paths
        """
        output_dir = Path(settings.DATASETS_DIR) / user_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        processed_paths = []
        
        for idx, image_path in enumerate(image_paths):
            output_path = str(output_dir / f"{idx:04d}.jpg")
            if self.process_image(image_path, output_path):
                processed_paths.append(output_path)
        
        return processed_paths
    
    def get_best_face_image(self, user_id: str) -> Optional[str]:
        """
        Get the best face image from processed dataset.
        Prefers larger file size (less compression, better quality).
        """
        dataset_dir = Path(settings.DATASETS_DIR) / user_id
        if not dataset_dir.exists():
            return None

        image_files = list(dataset_dir.glob("*.jpg"))
        if not image_files:
            return None

        # Prefer larger file (often better quality / frontal)
        best = max(image_files, key=lambda p: p.stat().st_size)
        return str(best)
