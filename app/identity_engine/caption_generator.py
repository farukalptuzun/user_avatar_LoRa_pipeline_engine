"""Auto caption generation for LoRA training images"""

import os
from pathlib import Path
from typing import List
from app.config.settings import settings


class CaptionGenerator:
    """Generate captions for LoRA training images"""
    
    @staticmethod
    def generate_caption(user_id: str) -> str:
        """
        Generate caption for user images
        
        Args:
            user_id: User ID
            
        Returns:
            Caption text in format "photo of <user_{id}> person"
        """
        return f"photo of <user_{user_id}> person"
    
    @staticmethod
    def create_caption_files(user_id: str, image_paths: List[str]) -> List[str]:
        """
        Create caption .txt files for each image
        
        Args:
            user_id: User ID
            image_paths: List of processed image paths
            
        Returns:
            List of caption file paths
        """
        caption_text = CaptionGenerator.generate_caption(user_id)
        caption_paths = []
        
        for image_path in image_paths:
            # Create .txt file with same name as image
            caption_path = str(Path(image_path).with_suffix('.txt'))
            
            with open(caption_path, 'w', encoding='utf-8') as f:
                f.write(caption_text)
            
            caption_paths.append(caption_path)
        
        return caption_paths
    
    @staticmethod
    def ensure_captions_exist(user_id: str) -> int:
        """
        Ensure all images in dataset have caption files
        
        Args:
            user_id: User ID
            
        Returns:
            Number of caption files created
        """
        dataset_dir = Path(settings.DATASETS_DIR) / user_id
        if not dataset_dir.exists():
            return 0
        
        caption_text = CaptionGenerator.generate_caption(user_id)
        created_count = 0
        
        # Find all images without captions
        for image_file in dataset_dir.glob("*.jpg"):
            caption_file = image_file.with_suffix('.txt')
            
            if not caption_file.exists():
                with open(caption_file, 'w', encoding='utf-8') as f:
                    f.write(caption_text)
                created_count += 1
        
        return created_count
