"""Color correction and grading for video"""

import cv2
import numpy as np
from typing import Optional, Tuple


class ColorCorrector:
    """Apply color correction to video"""
    
    def __init__(
        self,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        gamma: float = 1.0
    ):
        """
        Initialize color corrector
        
        Args:
            brightness: Brightness adjustment (0.0-2.0)
            contrast: Contrast adjustment (0.0-2.0)
            saturation: Saturation adjustment (0.0-2.0)
            gamma: Gamma correction (0.0-3.0)
        """
        self.brightness = brightness
        self.contrast = contrast
        self.saturation = saturation
        self.gamma = gamma
    
    def correct_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply color correction to a single frame
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Color-corrected frame
        """
        corrected = frame.copy().astype(np.float32)
        
        # Brightness adjustment
        if self.brightness != 1.0:
            corrected = corrected * self.brightness
        
        # Contrast adjustment
        if self.contrast != 1.0:
            corrected = cv2.convertScaleAbs(corrected, alpha=self.contrast, beta=0)
        
        # Gamma correction
        if self.gamma != 1.0:
            inv_gamma = 1.0 / self.gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255
                            for i in np.arange(0, 256)]).astype("uint8")
            corrected = cv2.LUT(corrected.astype(np.uint8), table).astype(np.float32)
        
        # Saturation adjustment (convert to HSV, adjust S channel)
        if self.saturation != 1.0:
            hsv = cv2.cvtColor(corrected.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:, :, 1] = hsv[:, :, 1] * self.saturation
            hsv = np.clip(hsv, 0, 255)
            corrected = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
        
        # Clip values to valid range
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)
        
        return corrected
    
    def correct_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Apply color correction to entire video
        
        Args:
            video_path: Path to input video
            output_path: Path to save corrected video
            
        Returns:
            Path to corrected video if successful, None otherwise
        """
        if output_path is None:
            output_path = video_path.replace('.mp4', '_corrected.mp4')
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            corrected_frame = self.correct_frame(frame)
            out.write(corrected_frame)
        
        cap.release()
        out.release()
        
        return output_path
