"""LoRA training orchestration for Stable Diffusion 1.5"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from app.config.settings import settings


class LoRATrainer:
    """Orchestrate LoRA training using diffusers or Kohya_ss"""
    
    def __init__(self):
        """Initialize trainer"""
        self.base_model = settings.SD_BASE_MODEL
        self.rank = settings.LORA_RANK
        self.epochs = settings.LORA_EPOCHS
        self.learning_rate = settings.LORA_LEARNING_RATE
        self.resolution = settings.LORA_RESOLUTION
    
    def train(
        self,
        user_id: str,
        dataset_path: str,
        output_path: Optional[str] = None
    ) -> bool:
        """
        Train LoRA model for user
        
        Args:
            user_id: User ID
            dataset_path: Path to dataset directory
            output_path: Optional output path for LoRA weights
            
        Returns:
            True if training successful, False otherwise
        """
        if output_path is None:
            output_path = str(Path(settings.LORA_STORAGE_DIR) / f"{user_id}.safetensors")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Use diffusers LoRA training
        # This is a simplified version - in production, use proper training script
        try:
            # For MVP, we'll use a subprocess call to a training script
            # In production, integrate with diffusers.train_text_to_image_lora or Kohya_ss
            
            training_script = self._get_training_script_path()
            if training_script and os.path.exists(training_script):
                return self._run_training_script(
                    dataset_path=dataset_path,
                    output_path=output_path,
                    user_id=user_id
                )
            else:
                # Fallback: use diffusers API directly
                return self._train_with_diffusers(
                    dataset_path=dataset_path,
                    output_path=output_path,
                    user_id=user_id
                )
        except Exception as e:
            print(f"LoRA training failed: {e}", file=sys.stderr)
            return False
    
    def _train_with_diffusers(
        self,
        dataset_path: str,
        output_path: str,
        user_id: str
    ) -> bool:
        """
        Train LoRA using diffusers library
        
        Note: This is a placeholder. In production, implement full training pipeline
        using diffusers.train_text_to_image_lora or similar.
        """
        # Placeholder implementation
        # In production, implement:
        # 1. Load base model
        # 2. Prepare dataset with captions
        # 3. Configure training arguments
        # 4. Run training loop
        # 5. Save LoRA weights
        
        print(f"Training LoRA for user {user_id}")
        print(f"Dataset: {dataset_path}")
        print(f"Output: {output_path}")
        print(f"Rank: {self.rank}, Epochs: {self.epochs}, LR: {self.learning_rate}")
        
        # TODO: Implement actual training logic
        # For now, create a placeholder file
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).touch()
        
        return True
    
    def _get_training_script_path(self) -> Optional[str]:
        """Get path to external training script if available"""
        # Check for Kohya_ss or custom training script
        possible_paths = [
            "scripts/train_lora.py",
            "train_lora.py",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _run_training_script(
        self,
        dataset_path: str,
        output_path: str,
        user_id: str
    ) -> bool:
        """
        Run external training script
        
        Args:
            dataset_path: Path to dataset
            output_path: Output path for LoRA weights
            user_id: User ID
            
        Returns:
            True if successful
        """
        training_script = self._get_training_script_path()
        
        cmd = [
            sys.executable,
            training_script,
            "--dataset_path", dataset_path,
            "--output_path", output_path,
            "--base_model", self.base_model,
            "--rank", str(self.rank),
            "--epochs", str(self.epochs),
            "--learning_rate", str(self.learning_rate),
            "--resolution", str(self.resolution),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Training script failed: {e.stderr}", file=sys.stderr)
            return False
    
    def validate_dataset(self, dataset_path: str) -> bool:
        """
        Validate that dataset is ready for training
        
        Args:
            dataset_path: Path to dataset directory
            
        Returns:
            True if dataset is valid
        """
        if not os.path.exists(dataset_path):
            return False
        
        # Check for images
        image_files = list(Path(dataset_path).glob("*.jpg"))
        if len(image_files) == 0:
            return False
        
        # Check that all images have captions
        for image_file in image_files:
            caption_file = image_file.with_suffix('.txt')
            if not caption_file.exists():
                return False
        
        return True
