"""Configuration management using Pydantic Settings"""

from pydantic_settings import BaseSettings
from typing import Optional, Tuple


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "lora_avatar"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # S3 Storage
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: Optional[str] = None
    
    # ElevenLabs TTS
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_DEFAULT_TURKISH_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Default Turkish voice
    
    # File Paths (RunPod için /workspace kullanılır)
    DATASETS_DIR: str = "/workspace/datasets"
    LORA_STORAGE_DIR: str = "/workspace/lora_storage"
    AUDIO_DIR: str = "/workspace/audio"
    VIDEO_RAW_DIR: str = "/workspace/video_raw"
    VIDEO_FINAL_DIR: str = "/workspace/video_final"
    
    # LoRA Training
    SD_BASE_MODEL: str = "runwayml/stable-diffusion-v1-5"
    LORA_RANK: int = 8
    LORA_EPOCHS: int = 12
    LORA_LEARNING_RATE: float = 1e-4
    LORA_RESOLUTION: int = 512
    
    # Video Settings
    VIDEO_MAX_DURATION_SECONDS: int = 30
    VIDEO_TARGET_RESOLUTION: Tuple[int, int] = (1280, 720)  # 720p
    VIDEO_TARGET_FPS: int = 25
    
    # Script Limits
    SCRIPT_MAX_CHARACTERS: int = 1000
    
    # Face Detection
    FACE_DETECTION_MODEL: str = "buffalo_l"
    
    # Retry Configuration
    ELEVENLABS_RETRY_ATTEMPTS: int = 2
    ELEVENLABS_RETRY_DELAY: int = 1  # seconds
    
    # Ngrok (optional)
    NGROK_AUTHTOKEN: Optional[str] = None
    
    # Celery Worker (optional)
    START_CELERY_WORKER: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings()
