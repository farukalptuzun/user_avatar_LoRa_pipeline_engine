"""Video upscaling using RealESRGAN"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from app.config.settings import settings


class VideoUpscaler:
    """Video upscaling using RealESRGAN"""
    
    def __init__(self, model_name: str = "RealESRGAN_x4plus"):
        """
        Initialize RealESRGAN upscaler
        
        Args:
            model_name: RealESRGAN model name
        """
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load RealESRGAN model"""
        try:
            from realesrgan import RealESRGANer
            from realesrgan.archs.srvgg_arch import SRVGGNetCompact
            
            # Initialize RealESRGAN
            if self.model_name == "RealESRGAN_x4plus":
                model_path = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'
                self.model = RealESRGANer(
                    scale=4,
                    model_path=model_path,
                    model=SRVGGNetCompact,
                    tile=0,
                    tile_pad=10,
                    pre_pad=0,
                    half=False
                )
            else:
                print(f"Model {self.model_name} not yet implemented")
                self.model = None
        except ImportError:
            print("RealESRGAN not available. Install with: pip install realesrgan")
            self.model = None
        except Exception as e:
            print(f"Failed to load RealESRGAN model: {e}")
            self.model = None
    
    def upscale_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Upscale a single frame
        
        Args:
            frame: Input frame (BGR format)
            
        Returns:
            Upscaled frame
        """
        if self.model is None:
            return frame
        
        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Upscale
            output, _ = self.model.enhance(frame_rgb, outscale=4)
            
            # Convert RGB back to BGR
            output_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
            
            return output_bgr
        except Exception as e:
            print(f"Frame upscaling failed: {e}")
            return frame
    
    def upscale_to_resolution(
        self,
        video_path: str,
        target_resolution: Tuple[int, int],
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Upscale video to target resolution
        
        Args:
            video_path: Path to input video
            target_resolution: Target (width, height)
            output_path: Path to save upscaled video
            
        Returns:
            Path to upscaled video if successful, None otherwise
        """
        target_width, target_height = target_resolution
        
        if output_path is None:
            output_path = video_path.replace('.mp4', f'_{target_width}x{target_height}.mp4')
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Calculate scale factor
        scale_x = target_width / width
        scale_y = target_height / height
        scale = max(scale_x, scale_y)
        
        # If model available and scale > 1, use RealESRGAN
        if self.model is not None and scale > 1.0:
            return self._upscale_with_model(video_path, target_resolution, output_path, fps)
        else:
            # Use simple resize
            return self._upscale_simple(video_path, target_resolution, output_path, fps)
    
    def _upscale_with_model(
        self,
        video_path: str,
        target_resolution: Tuple[int, int],
        output_path: str,
        fps: int
    ) -> Optional[str]:
        """Upscale using RealESRGAN model"""
        cap = cv2.VideoCapture(video_path)
        target_width, target_height = target_resolution
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
        
        frame_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Upscale frame
            upscaled = self.upscale_frame(frame)
            
            # Resize to exact target resolution if needed
            if upscaled.shape[1] != target_width or upscaled.shape[0] != target_height:
                upscaled = cv2.resize(upscaled, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
            
            out.write(upscaled)
            
            frame_count += 1
            if frame_count % 30 == 0:
                print(f"Upscaled {frame_count} frames...")
        
        cap.release()
        out.release()
        
        return output_path
    
    def _upscale_simple(
        self,
        video_path: str,
        target_resolution: Tuple[int, int],
        output_path: str,
        fps: int
    ) -> Optional[str]:
        """Simple upscale using OpenCV resize"""
        cap = cv2.VideoCapture(video_path)
        target_width, target_height = target_resolution
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (target_width, target_height))
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
            out.write(resized)
        
        cap.release()
        out.release()
        
        return output_path
