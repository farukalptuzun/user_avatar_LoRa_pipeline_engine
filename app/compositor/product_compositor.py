"""Product compositor for combining avatar video with product images"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from app.config.settings import settings


class ProductCompositor:
    """Compose avatar video with product image"""
    
    def __init__(self):
        """Initialize compositor"""
        self.avatar_width_ratio = 0.6  # Avatar takes 60% of width
        self.product_width_ratio = 0.4  # Product takes 40% of width
    
    def remove_background(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Remove background from avatar video using segmentation
        
        Args:
            video_path: Path to input video
            output_path: Path to save video with transparent background
            
        Returns:
            Path to output video if successful, None otherwise
        """
        try:
            from rembg import remove
            import imageio
            
            # Read video
            reader = imageio.get_reader(video_path)
            fps = reader.get_meta_data()['fps']
            
            # Process frames
            frames = []
            for frame in reader:
                # Remove background
                output = remove(frame)
                frames.append(output)
            
            # Save video with alpha channel
            if output_path is None:
                output_path = video_path.replace('.mp4', '_no_bg.mp4')
            
            writer = imageio.get_writer(
                output_path,
                fps=fps,
                codec='libx264',
                pixelformat='yuva420p'
            )
            
            for frame in frames:
                writer.append_data(frame)
            
            writer.close()
            
            return output_path
        except ImportError:
            # Fallback: use OpenCV-based approach (simpler but less accurate)
            return self._remove_background_opencv(video_path, output_path)
    
    def _remove_background_opencv(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Remove background using OpenCV (simpler fallback)
        
        Args:
            video_path: Path to input video
            output_path: Path to save output
            
        Returns:
            Output path
        """
        cap = cv2.VideoCapture(video_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if output_path is None:
            output_path = video_path.replace('.mp4', '_no_bg.mp4')
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Simple background removal using color-based segmentation
        # In production, use more sophisticated methods
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Convert to HSV for better color segmentation
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Create mask (simplified - assumes background is relatively uniform)
            # In production, use proper segmentation model
            mask = cv2.inRange(hsv, (0, 0, 200), (180, 30, 255))
            mask = cv2.bitwise_not(mask)
            
            # Apply mask
            result = cv2.bitwise_and(frame, frame, mask=mask)
            out.write(result)
        
        cap.release()
        out.release()
        
        return output_path
    
    def resize_product_image(
        self,
        product_image_path: str,
        target_size: Tuple[int, int],
        output_path: Optional[str] = None
    ) -> str:
        """
        Resize product image to target size while maintaining aspect ratio
        
        Args:
            product_image_path: Path to product image
            target_size: Target (width, height)
            output_path: Path to save resized image
            
        Returns:
            Path to resized image
        """
        img = cv2.imread(product_image_path)
        if img is None:
            raise ValueError(f"Could not load image: {product_image_path}")
        
        target_width, target_height = target_size
        
        # Maintain aspect ratio
        h, w = img.shape[:2]
        aspect_ratio = w / h
        
        if aspect_ratio > target_width / target_height:
            # Image is wider
            new_width = target_width
            new_height = int(target_width / aspect_ratio)
        else:
            # Image is taller
            new_height = target_height
            new_width = int(target_height * aspect_ratio)
        
        resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # Create canvas with target size and center image
        canvas = np.ones((target_height, target_width, 3), dtype=np.uint8) * 255
        
        y_offset = (target_height - new_height) // 2
        x_offset = (target_width - new_width) // 2
        
        canvas[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = resized
        
        if output_path is None:
            output_path = product_image_path.replace('.jpg', '_resized.jpg').replace('.png', '_resized.png')
        
        cv2.imwrite(output_path, canvas)
        return output_path
    
    def compose_video(
        self,
        avatar_video_path: str,
        product_image_path: str,
        output_path: Optional[str] = None,
        video_width: int = 1280,
        video_height: int = 720
    ) -> Optional[str]:
        """
        Compose avatar video with product image side by side
        
        Args:
            avatar_video_path: Path to avatar video (with or without background)
            product_image_path: Path to product image
            output_path: Path to save composed video
            video_width: Final video width
            video_height: Final video height
            
        Returns:
            Path to composed video if successful, None otherwise
        """
        if output_path is None:
            output_path = avatar_video_path.replace('.mp4', '_composed.mp4')
        
        try:
            # Load avatar video
            avatar_clip = VideoFileClip(avatar_video_path)
            
            # Calculate dimensions
            avatar_width = int(video_width * self.avatar_width_ratio)
            product_width = int(video_width * self.product_width_ratio)
            
            # Resize avatar video
            avatar_clip = avatar_clip.resize(width=avatar_width)
            
            # Resize product image
            resized_product_path = self.resize_product_image(
                product_image_path,
                (product_width, video_height)
            )
            
            # Create product image clip (static, same duration as video)
            product_clip = ImageClip(resized_product_path).set_duration(avatar_clip.duration)
            product_clip = product_clip.set_position(('right', 'center'))
            
            # Position avatar on left
            avatar_clip = avatar_clip.set_position(('left', 'center'))
            
            # Compose video
            final_clip = CompositeVideoClip(
                [avatar_clip, product_clip],
                size=(video_width, video_height)
            )
            
            # Write output
            final_clip.write_videofile(
                output_path,
                fps=avatar_clip.fps,
                codec='libx264',
                audio_codec='aac'
            )
            
            # Cleanup
            avatar_clip.close()
            product_clip.close()
            final_clip.close()
            
            # Remove temporary resized product image
            if os.path.exists(resized_product_path) and resized_product_path != product_image_path:
                os.remove(resized_product_path)
            
            return output_path
        except Exception as e:
            print(f"Video composition failed: {e}")
            return None
    
    def process_with_product(
        self,
        avatar_video_path: str,
        product_image_path: str,
        output_path: Optional[str] = None,
        remove_bg: bool = True
    ) -> Optional[str]:
        """
        Complete pipeline: remove background and compose with product
        
        Args:
            avatar_video_path: Path to avatar video
            product_image_path: Path to product image
            output_path: Path to save final video
            remove_bg: Whether to remove background from avatar
            
        Returns:
            Path to final composed video
        """
        video_to_compose = avatar_video_path
        
        # Remove background if requested
        if remove_bg:
            bg_removed_path = self.remove_background(avatar_video_path)
            if bg_removed_path:
                video_to_compose = bg_removed_path
        
        # Compose video
        composed_path = self.compose_video(
            video_to_compose,
            product_image_path,
            output_path
        )
        
        # Cleanup temporary background-removed video
        if remove_bg and bg_removed_path and bg_removed_path != avatar_video_path:
            if os.path.exists(bg_removed_path):
                os.remove(bg_removed_path)
        
        return composed_path
