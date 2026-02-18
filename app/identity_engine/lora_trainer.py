"""LoRA training orchestration for Stable Diffusion 1.5"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Dict
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from torchvision import transforms
from diffusers import (
    AutoencoderKL,
    UNet2DConditionModel,
    DDPMScheduler,
    StableDiffusionPipeline,
)
from transformers import CLIPTokenizer, CLIPTextModel
from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
import safetensors.torch
from app.config.settings import settings


class ImageCaptionDataset(Dataset):
    """Dataset for image-caption pairs"""
    
    def __init__(self, dataset_path: str, resolution: int = 512):
        """
        Initialize dataset
        
        Args:
            dataset_path: Path to dataset directory containing images and .txt caption files
            resolution: Target image resolution
        """
        self.dataset_path = Path(dataset_path)
        self.resolution = resolution
        
        # Find all image files
        self.image_files = sorted(self.dataset_path.glob("*.jpg")) + sorted(self.dataset_path.glob("*.png"))
        
        if len(self.image_files) == 0:
            raise ValueError(f"No images found in {dataset_path}")
        
        # Load captions
        self.captions = []
        for img_file in self.image_files:
            caption_file = img_file.with_suffix('.txt')
            if caption_file.exists():
                with open(caption_file, 'r', encoding='utf-8') as f:
                    caption = f.read().strip()
                    self.captions.append(caption)
            else:
                # Fallback: use filename as caption
                self.captions.append(f"photo of {img_file.stem}")
        
        # Image transforms
        self.transform = transforms.Compose([
            transforms.Resize((resolution, resolution)),
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5])  # Normalize to [-1, 1]
        ])
    
    def __len__(self):
        return len(self.image_files)
    
    def __getitem__(self, idx):
        img_path = self.image_files[idx]
        caption = self.captions[idx]
        
        # Load and preprocess image
        image = Image.open(img_path).convert("RGB")
        pixel_values = self.transform(image)
        
        return {
            "pixel_values": pixel_values,
            "caption": caption
        }


class LoRATrainer:
    """Orchestrate LoRA training using diffusers and peft"""
    
    def __init__(self):
        """Initialize trainer"""
        self.base_model = settings.SD_BASE_MODEL
        self.rank = settings.LORA_RANK
        self.epochs = settings.LORA_EPOCHS
        self.learning_rate = settings.LORA_LEARNING_RATE
        self.resolution = settings.LORA_RESOLUTION
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
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
        Train LoRA adapter using diffusers and peft libraries
        
        Args:
            dataset_path: Path to dataset directory
            output_path: Output path for LoRA weights (.safetensors)
            user_id: User ID for logging
            
        Returns:
            True if training successful, False otherwise
        """
        print(f"[LoRA Trainer] Starting LoRA training for user {user_id}")
        print(f"[LoRA Trainer] Device: {self.device}")
        print(f"[LoRA Trainer] Dataset: {dataset_path}")
        print(f"[LoRA Trainer] Output: {output_path}")
        print(f"[LoRA Trainer] Rank: {self.rank}, Epochs: {self.epochs}, LR: {self.learning_rate}")
        
        try:
            # Load dataset
            print(f"[LoRA Trainer] Loading dataset from {dataset_path}...")
            train_dataset = ImageCaptionDataset(dataset_path, resolution=self.resolution)
            dataloader = DataLoader(
                train_dataset,
                batch_size=1,
                shuffle=True,
                num_workers=0  # Set to 0 to avoid multiprocessing issues
            )
            print(f"[LoRA Trainer] Dataset loaded: {len(train_dataset)} images")
            
            # Load Stable Diffusion components
            print(f"[LoRA Trainer] Loading Stable Diffusion model: {self.base_model}...")
            model_id = self.base_model
            
            # Load VAE
            vae = AutoencoderKL.from_pretrained(
                model_id,
                subfolder="vae",
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            vae.requires_grad_(False)
            vae.eval()
            
            # Load tokenizer and text encoder
            tokenizer = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
            text_encoder = CLIPTextModel.from_pretrained(
                model_id,
                subfolder="text_encoder",
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            text_encoder.requires_grad_(False)
            text_encoder.eval()
            
            # Load UNet
            unet = UNet2DConditionModel.from_pretrained(
                model_id,
                subfolder="unet",
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32
            ).to(self.device)
            
            # Configure LoRA
            print(f"[LoRA Trainer] Configuring LoRA adapter (rank={self.rank})...")
            lora_config = LoraConfig(
                r=self.rank,
                lora_alpha=self.rank,  # Typically same as rank
                target_modules=["to_k", "to_q", "to_v", "to_out.0"],  # Attention layers
                lora_dropout=0.0,
                bias="none",
            )
            
            # Apply LoRA to UNet
            unet = get_peft_model(unet, lora_config)
            unet.print_trainable_parameters()
            
            # Load noise scheduler
            noise_scheduler = DDPMScheduler.from_pretrained(model_id, subfolder="scheduler")
            
            # Setup optimizer
            optimizer = torch.optim.AdamW(
                unet.parameters(),
                lr=self.learning_rate,
                betas=(0.9, 0.999),
                weight_decay=0.01,
                eps=1e-8
            )
            
            # Training loop
            print(f"[LoRA Trainer] Starting training for {self.epochs} epochs...")
            unet.train()
            global_step = 0
            
            for epoch in range(self.epochs):
                print(f"[LoRA Trainer] Epoch {epoch + 1}/{self.epochs}")
                epoch_loss = 0.0
                
                for batch_idx, batch in enumerate(dataloader):
                    pixel_values = batch["pixel_values"].to(self.device, dtype=torch.float16 if self.device.type == "cuda" else torch.float32)
                    captions = batch["caption"]
                    
                    # Encode text
                    with torch.no_grad():
                        text_inputs = tokenizer(
                            captions,
                            padding="max_length",
                            max_length=tokenizer.model_max_length,
                            truncation=True,
                            return_tensors="pt",
                        )
                        text_input_ids = text_inputs.input_ids.to(self.device)
                        encoder_hidden_states = text_encoder(text_input_ids)[0]
                    
                    # Encode images to latents
                    with torch.no_grad():
                        latents = vae.encode(pixel_values).latent_dist.sample()
                        latents = latents * vae.config.scaling_factor
                    
                    # Sample noise
                    noise = torch.randn_like(latents)
                    timesteps = torch.randint(
                        0,
                        noise_scheduler.config.num_train_timesteps,
                        (latents.shape[0],),
                        device=self.device,
                        dtype=torch.long,
                    )
                    
                    # Add noise to latents
                    noisy_latents = noise_scheduler.add_noise(latents, noise, timesteps)
                    
                    # Predict noise
                    model_pred = unet(
                        noisy_latents,
                        timesteps,
                        encoder_hidden_states=encoder_hidden_states,
                    ).sample
                    
                    # Calculate loss
                    loss = torch.nn.functional.mse_loss(model_pred.float(), noise.float(), reduction="mean")
                    
                    # Backward pass
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(unet.parameters(), 1.0)
                    optimizer.step()
                    
                    epoch_loss += loss.item()
                    global_step += 1
                    
                    if global_step % 10 == 0:
                        print(f"[LoRA Trainer] Step {global_step}, Loss: {loss.item():.6f}")
                
                avg_loss = epoch_loss / len(dataloader)
                print(f"[LoRA Trainer] Epoch {epoch + 1} completed, Average Loss: {avg_loss:.6f}")
            
            # Save LoRA weights
            print(f"[LoRA Trainer] Saving LoRA weights to {output_path}...")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Get LoRA state dict
            lora_state_dict = unet.get_peft_state_dict()
            
            # Save as safetensors
            safetensors.torch.save_file(lora_state_dict, output_path)
            print(f"[LoRA Trainer] LoRA weights saved successfully!")
            
            # Also save in diffusers format (optional, for compatibility)
            output_dir = Path(output_path).parent / f"{user_id}_lora"
            output_dir.mkdir(parents=True, exist_ok=True)
            unet.save_pretrained(str(output_dir))
            print(f"[LoRA Trainer] LoRA adapter also saved to {output_dir}")
            
            print(f"[LoRA Trainer] Training completed successfully!")
            return True
            
        except Exception as e:
            print(f"[LoRA Trainer] Training failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
    
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
