"""Face restoration using GFPGAN"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional
from app.config.settings import settings


class FaceRestorer:
    """Face restoration using GFPGAN"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize GFPGAN face restorer
        
        Args:
            model_path: Path to GFPGAN model (optional)
        """
        self.model_path = model_path
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load GFPGAN model"""
        try:
            from gfpgan import GFPGANer
            
            # Initialize GFPGAN (use settings path: /workspace/SadTalker/gfpgan/weights/GFPGANv1.4.pth)
            model_path = self.model_path or settings.GFPGAN_MODEL_PATH
            self.model = GFPGANer(
                model_path=model_path,
                upscale=1,
                arch='clean',
                channel_multiplier=2,
                bg_upsampler=None
            )
        except ImportError:
            print("GFPGAN not available. Install with: pip install gfpgan")
            self.model = None
        except Exception as e:
            print(f"Failed to load GFPGAN model: {e}")
            self.model = None
    
    def restore_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Restore face in a single frame
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Restored frame
        """
        if self.model is None:
            return frame
        
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Restore face
            _, _, restored_frame = self.model.enhance(
                frame_rgb,
                has_aligned=False,
                only_center_face=False,
                paste_back=True,
                weight=0.5
            )
            
            # Convert RGB back to BGR
            restored_bgr = cv2.cvtColor(restored_frame, cv2.COLOR_RGB2BGR)
            
            return restored_bgr
        except Exception as e:
            print(f"Face restoration failed for frame: {e}")
            return frame
    
    def restore_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Restore faces in video using GFPGAN
        
        Args:
            video_path: Path to input video
            output_path: Path to save restored video
            
        Returns:
            Path to restored video if successful, None otherwise
        """
        if self.model is None:
            print("GFPGAN model not available, skipping face restoration")
            return video_path
        
        if output_path is None:
            output_path = video_path.replace('.mp4', '_restored.mp4')
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Restore face in frame
            restored_frame = self.restore_frame(frame)
            out.write(restored_frame)
            
            frame_count += 1
            if frame_count % 30 == 0:
                print(f"Processed {frame_count} frames...")
        
        cap.release()
        out.release()
        
        return output_path
