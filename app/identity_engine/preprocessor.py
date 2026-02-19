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
    
    def detect_and_align_face(self, image_path: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Detect and align face from image
        
        Args:
            image_path: Path to input image
            
        Returns:
            Tuple of (aligned_face_image, original_image) or None if no face detected
        """
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        faces = self.app.get(img)
        if len(faces) == 0:
            return None
        
        # Use the largest face
        face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        
        # Get face landmarks for alignment
        landmarks = face.landmark_2d_106.astype(np.int32)
        
        # Align face using landmarks
        aligned_face = self._align_face(img, landmarks)
        
        return aligned_face, img
    
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
    
    def crop_to_square(self, img: np.ndarray, size: int = 512) -> np.ndarray:
        """
        Crop image to square and resize to target size
        
        Args:
            img: Input image
            size: Target size (default 512)
            
        Returns:
            Cropped and resized image
        """
        h, w = img.shape[:2]
        min_dim = min(h, w)
        
        # Crop to square from center
        start_y = (h - min_dim) // 2
        start_x = (w - min_dim) // 2
        cropped = img[start_y:start_y + min_dim, start_x:start_x + min_dim]
        
        # Resize to target size
        resized = cv2.resize(cropped, (size, size), interpolation=cv2.INTER_LANCZOS4)
        
        return resized
    
    def process_image(self, image_path: str, output_path: str) -> bool:
        """
        Process single image: detect face, align, crop to 512x512
        
        Args:
            image_path: Path to input image
            output_path: Path to save processed image
            
        Returns:
            True if successful, False otherwise
        """
        result = self.detect_and_align_face(image_path)
        if result is None:
            return False
        
        aligned_face, _ = result
        
        # Crop to square 512x512
        cropped = self.crop_to_square(aligned_face, size=settings.LORA_RESOLUTION)
        
        # Save processed image
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
        Get the best quality face image from processed dataset
        
        Args:
            user_id: User ID
            
        Returns:
            Path to best face image or None
        """
        dataset_dir = Path(settings.DATASETS_DIR) / user_id
        if not dataset_dir.exists():
            return None
        
        # For now, return the first image
        # In production, could implement quality scoring
        image_files = sorted(dataset_dir.glob("*.jpg"))
        if image_files:
            return str(image_files[0])
        
        return None
