"""Temporal smoothing for video frames"""

import cv2
import numpy as np
from typing import Optional
from collections import deque


class TemporalSmoother:
    """Apply temporal smoothing to video frames"""
    
    def __init__(self, buffer_size: int = 5, alpha: float = 0.3):
        """
        Initialize temporal smoother
        
        Args:
            buffer_size: Number of frames to buffer for smoothing
            alpha: Smoothing factor (0.0-1.0), higher = more smoothing
        """
        self.buffer_size = buffer_size
        self.alpha = alpha
        self.frame_buffer = deque(maxlen=buffer_size)
    
    def smooth_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Smooth a single frame using temporal information
        
        Args:
            frame: Input frame
            
        Returns:
            Smoothed frame
        """
        self.frame_buffer.append(frame.astype(np.float32))
        
        if len(self.frame_buffer) < 2:
            return frame
        
        # Weighted average of recent frames
        smoothed = np.zeros_like(frame, dtype=np.float32)
        total_weight = 0.0
        
        for i, buffered_frame in enumerate(self.frame_buffer):
            # More recent frames get higher weight
            weight = (1 - self.alpha) ** (len(self.frame_buffer) - i - 1)
            smoothed += buffered_frame * weight
            total_weight += weight
        
        smoothed = smoothed / total_weight
        
        return smoothed.astype(np.uint8)
    
    def smooth_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Apply temporal smoothing to entire video
        
        Args:
            video_path: Path to input video
            output_path: Path to save smoothed video
            
        Returns:
            Path to smoothed video if successful, None otherwise
        """
        if output_path is None:
            output_path = video_path.replace('.mp4', '_smoothed.mp4')
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Reset buffer
        self.frame_buffer.clear()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            smoothed_frame = self.smooth_frame(frame)
            out.write(smoothed_frame)
        
        cap.release()
        out.release()
        
        return output_path
