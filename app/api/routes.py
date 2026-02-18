"""FastAPI routes for avatar pipeline"""

import os
import uuid
import base64
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pymongo.database import Database
from app.api.models import (
    TrainIdentityRequest,
    TrainingStatusResponse,
    GenerateVideoRequest,
    JobResponse,
    VideoDownloadResponse,
)
from app.api.dependencies import get_db
from app.database.models import (
    USERS_COLLECTION,
    JOBS_COLLECTION,
    TrainingStatus,
    JobStatus,
    user_doc,
    job_doc,
)
from app.queue.tasks import train_identity_task, generate_video_task
from app.tts_engine.voice_manager import VoiceManager
from app.storage.s3_client import S3Client
from app.config.settings import settings

router = APIRouter(prefix=settings.API_V1_PREFIX, tags=["avatar"])


@router.post("/upload-photos", response_model=dict)
async def upload_photos(
    user_id: str = Form(...),
    photos: List[UploadFile] = File(...),
    db: Database = Depends(get_db)
):
    """
    Upload photos for user identity creation
    
    Args:
        user_id: User ID
        photos: List of photo files
        
    Returns:
        Dictionary with uploaded file paths
    """
    if len(photos) == 0:
        raise HTTPException(status_code=400, detail="At least one photo is required")
    
    users = db[USERS_COLLECTION]
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one(user_doc(user_id=user_id))
    
    # Save uploaded photos
    uploaded_paths = []
    upload_dir = Path(settings.DATASETS_DIR) / user_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, photo in enumerate(photos):
        # Validate file type
        if not photo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File {photo.filename} is not an image")
        
        # Save file
        file_extension = Path(photo.filename).suffix or ".jpg"
        file_path = upload_dir / f"{idx:04d}{file_extension}"
        
        with open(file_path, "wb") as f:
            content = await photo.read()
            f.write(content)
        
        uploaded_paths.append(str(file_path))
    
    return {
        "user_id": user_id,
        "uploaded_files": uploaded_paths,
        "count": len(uploaded_paths)
    }


@router.post("/train-identity", response_model=dict)
async def train_identity(
    request: TrainIdentityRequest,
    db: Database = Depends(get_db)
):
    """
    Trigger LoRA training for user identity
    
    Args:
        request: Training request with user_id
        
    Returns:
        Dictionary with training job status
    """
    users = db[USERS_COLLECTION]
    user = users.find_one({"user_id": request.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    status = user.get("training_status", TrainingStatus.PENDING.value)
    if status == TrainingStatus.PROCESSING.value:
        raise HTTPException(status_code=400, detail="Training already in progress")
    
    if status == TrainingStatus.COMPLETED.value:
        return {
            "user_id": request.user_id,
            "status": "already_completed",
            "lora_path": user.get("lora_path")
        }
    
    # Get uploaded photos
    upload_dir = Path(settings.DATASETS_DIR) / request.user_id / "uploads"
    if not upload_dir.exists():
        raise HTTPException(status_code=400, detail="No photos uploaded for this user")
    
    image_paths = [str(p) for p in upload_dir.glob("*") if p.suffix.lower() in [".jpg", ".jpeg", ".png"]]
    
    if len(image_paths) == 0:
        raise HTTPException(status_code=400, detail="No valid images found")
    
    # Trigger async training task
    task = train_identity_task.delay(request.user_id, image_paths)
    
    return {
        "user_id": request.user_id,
        "task_id": task.id,
        "status": "processing"
    }


@router.get("/training-status/{user_id}", response_model=TrainingStatusResponse)
async def get_training_status(
    user_id: str,
    db: Database = Depends(get_db)
):
    """
    Get training status for user
    
    Args:
        user_id: User ID
        
    Returns:
        Training status response
    """
    user = db[USERS_COLLECTION].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    status_val = user.get("training_status", TrainingStatus.PENDING.value)
    status_enum = TrainingStatus(status_val) if isinstance(status_val, str) else status_val
    return TrainingStatusResponse(
        user_id=user["user_id"],
        status=status_enum,
        lora_path=user.get("lora_path")
    )


@router.post("/generate-video", response_model=JobResponse)
async def generate_video(
    request: GenerateVideoRequest,
    db: Database = Depends(get_db)
):
    """
    Submit video generation job
    
    Args:
        request: Video generation request
        
    Returns:
        Job response with job_id
    """
    users = db[USERS_COLLECTION]
    user = users.find_one({"user_id": request.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("training_status") != TrainingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"User identity not trained. Status: {user.get('training_status')}"
        )
    
    voice_id = user.get("voice_id")
    if request.voice_sample:
        voice_manager = VoiceManager()
        voice_sample_path = f"/tmp/voice_{request.user_id}_{uuid.uuid4().hex}.wav"
        
        if request.voice_sample.startswith("data:"):
            base64_data = request.voice_sample.split(",")[1]
            voice_data = base64.b64decode(base64_data)
        else:
            voice_data = base64.b64decode(request.voice_sample)
        
        with open(voice_sample_path, "wb") as f:
            f.write(voice_data)
        
        new_voice_id = voice_manager.create_user_voice(request.user_id, voice_sample_path)
        if new_voice_id:
            voice_id = new_voice_id
            from datetime import datetime
            users.update_one(
                {"user_id": request.user_id},
                {"$set": {"voice_id": voice_id, "updated_at": datetime.utcnow()}}
            )
        
        if os.path.exists(voice_sample_path):
            os.remove(voice_sample_path)
    
    # Handle product image if provided
    product_image_path = None
    if request.product_image:
        # Save product image
        product_dir = Path(settings.DATASETS_DIR) / request.user_id / "products"
        product_dir.mkdir(parents=True, exist_ok=True)
        product_image_path = str(product_dir / f"{uuid.uuid4().hex}.jpg")
        
        # Decode base64 if needed
        if request.product_image.startswith("data:"):
            base64_data = request.product_image.split(",")[1]
            image_data = base64.b64decode(base64_data)
        else:
            image_data = base64.b64decode(request.product_image)
        
        with open(product_image_path, "wb") as f:
            f.write(image_data)
    
    job_id = str(uuid.uuid4())
    jobs = db[JOBS_COLLECTION]
    doc = job_doc(
        job_id=job_id,
        user_id=request.user_id,
        script_text=request.script_text,
        product_image_path=product_image_path,
    )
    jobs.insert_one(doc)
    
    generate_video_task.delay(job_id)
    
    return JobResponse(
        job_id=doc["job_id"],
        user_id=doc["user_id"],
        status=JobStatus(doc["status"]),
        script_text=doc["script_text"],
        product_image_path=doc["product_image_path"],
        video_path=doc.get("video_path"),
        s3_url=doc.get("s3_url"),
        error_message=doc.get("error_message"),
        created_at=doc["created_at"],
        completed_at=doc.get("completed_at")
    )


@router.get("/job-status/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    db: Database = Depends(get_db)
):
    """
    Get job status
    
    Args:
        job_id: Job ID
        
    Returns:
        Job response
    """
    job = db[JOBS_COLLECTION].find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status_val = job.get("status", JobStatus.PENDING.value)
    status_enum = JobStatus(status_val) if isinstance(status_val, str) else status_val
    return JobResponse(
        job_id=job["job_id"],
        user_id=job["user_id"],
        status=status_enum,
        script_text=job["script_text"],
        product_image_path=job.get("product_image_path"),
        video_path=job.get("video_path"),
        s3_url=job.get("s3_url"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at")
    )


@router.get("/video/{job_id}", response_model=VideoDownloadResponse)
async def download_video(
    job_id: str,
    db: Database = Depends(get_db)
):
    """
    Get video download URL
    
    Args:
        job_id: Job ID
        
    Returns:
        Video download response with presigned URL or direct file
    """
    job = db[JOBS_COLLECTION].find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status_val = job.get("status", JobStatus.PENDING.value)
    if status_val != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {status_val}")
    
    if job.get("s3_url"):
        s3_client = S3Client()
        s3_key = s3_client.extract_key_from_url(job["s3_url"])
        if s3_key:
            presigned_url = s3_client.generate_presigned_url(s3_key)
            if presigned_url:
                return VideoDownloadResponse(download_url=presigned_url)
    
    video_path = job.get("video_path")
    if video_path and os.path.exists(video_path):
        return FileResponse(
            video_path,
            media_type="video/mp4",
            filename=f"{job_id}.mp4"
        )
    
    raise HTTPException(status_code=404, detail="Video file not found")
