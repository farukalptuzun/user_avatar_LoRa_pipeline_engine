"""MongoDB document models and enums"""

from datetime import datetime
from typing import Optional, Any
import enum

# Collection names
USERS_COLLECTION = "users"
JOBS_COLLECTION = "jobs"


class TrainingStatus(str, enum.Enum):
    """Training status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def user_doc(
    user_id: str,
    lora_path: Optional[str] = None,
    voice_id: Optional[str] = None,
    training_status: str = TrainingStatus.PENDING.value,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build a user document for MongoDB."""
    now = datetime.utcnow()
    return {
        "user_id": user_id,
        "lora_path": lora_path,
        "voice_id": voice_id,
        "training_status": training_status,
        "created_at": created_at or now,
        "updated_at": updated_at or now,
    }


def job_doc(
    job_id: str,
    user_id: str,
    script_text: str,
    product_image_path: Optional[str] = None,
    status: str = JobStatus.PENDING.value,
    video_path: Optional[str] = None,
    s3_url: Optional[str] = None,
    error_message: Optional[str] = None,
    created_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Build a job document for MongoDB."""
    now = datetime.utcnow()
    return {
        "job_id": job_id,
        "user_id": user_id,
        "script_text": script_text,
        "product_image_path": product_image_path,
        "status": status,
        "video_path": video_path,
        "s3_url": s3_url,
        "error_message": error_message,
        "created_at": created_at or now,
        "completed_at": completed_at,
    }
