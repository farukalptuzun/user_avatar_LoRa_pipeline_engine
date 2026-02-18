"""Pydantic models for API request/response validation"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.database.models import TrainingStatus, JobStatus


class PhotoUploadRequest(BaseModel):
    """Request model for photo upload"""
    user_id: str = Field(..., description="User ID")
    photos: List[str] = Field(..., description="List of base64 encoded images or file paths")


class TrainIdentityRequest(BaseModel):
    """Request model for identity training"""
    user_id: str = Field(..., description="User ID")


class TrainingStatusResponse(BaseModel):
    """Response model for training status"""
    user_id: str
    status: TrainingStatus
    lora_path: Optional[str] = None
    error_message: Optional[str] = None


class GenerateVideoRequest(BaseModel):
    """Request model for video generation"""
    user_id: str = Field(..., description="User ID")
    script_text: str = Field(..., description="Script text (max 1000 characters)")
    product_image: Optional[str] = Field(None, description="Optional product image path or base64")
    voice_sample: Optional[str] = Field(None, description="Optional voice sample for custom voice")
    
    @validator('script_text')
    def validate_script_length(cls, v):
        from app.config.settings import settings
        if len(v) > settings.SCRIPT_MAX_CHARACTERS:
            raise ValueError(
                f"Script exceeds maximum length of {settings.SCRIPT_MAX_CHARACTERS} characters"
            )
        if len(v.strip()) == 0:
            raise ValueError("Script cannot be empty")
        return v


class JobResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    user_id: str
    status: JobStatus
    script_text: str
    product_image_path: Optional[str] = None
    video_path: Optional[str] = None
    s3_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class VideoDownloadResponse(BaseModel):
    """Response model for video download"""
    download_url: str
    expires_at: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
