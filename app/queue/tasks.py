"""Celery tasks for pipeline processing"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from app.queue.celery_app import celery_app
from app.config.settings import settings
from app.database.models import (
    USERS_COLLECTION,
    JOBS_COLLECTION,
    TrainingStatus,
    JobStatus,
    user_doc,
)
from app.api.dependencies import get_database
from app.identity_engine.preprocessor import FacePreprocessor
from app.identity_engine.caption_generator import CaptionGenerator
from app.identity_engine.lora_trainer import LoRATrainer
from app.tts_engine.voice_manager import VoiceManager
from app.talking_head.sadtalker_wrapper import SadTalkerWrapper
from app.compositor.product_compositor import ProductCompositor
from app.enhancer.face_restore import FaceRestorer
from app.enhancer.upscaler import VideoUpscaler
from app.enhancer.temporal_smoothing import TemporalSmoother
from app.enhancer.color_correction import ColorCorrector
from app.storage.s3_client import S3Client


@celery_app.task(name="train_identity_task", bind=True, max_retries=3)
def train_identity_task(self, user_id: str, image_paths: list[str]):
    """
    Train LoRA identity for user
    
    Args:
        user_id: User ID
        image_paths: List of uploaded image paths
        
    Returns:
        Dictionary with training status and LoRA path
    """
    db = get_database()
    users = db[USERS_COLLECTION]
    try:
        user = users.find_one({"user_id": user_id})
        if not user:
            users.insert_one(user_doc(user_id=user_id, training_status=TrainingStatus.PROCESSING.value))
        else:
            users.update_one(
                {"user_id": user_id},
                {"$set": {"training_status": TrainingStatus.PROCESSING.value, "updated_at": datetime.utcnow()}}
            )
        
        preprocessor = FacePreprocessor()
        processed_paths = preprocessor.process_batch(image_paths, user_id)
        
        if not processed_paths:
            users.update_one(
                {"user_id": user_id},
                {"$set": {"training_status": TrainingStatus.FAILED.value, "updated_at": datetime.utcnow()}}
            )
            return {"status": "failed", "error": "No faces detected in images"}
        
        caption_generator = CaptionGenerator()
        caption_generator.create_caption_files(user_id, processed_paths)
        
        dataset_path = str(Path(settings.DATASETS_DIR) / user_id)
        trainer = LoRATrainer()
        
        if not trainer.validate_dataset(dataset_path):
            users.update_one(
                {"user_id": user_id},
                {"$set": {"training_status": TrainingStatus.FAILED.value, "updated_at": datetime.utcnow()}}
            )
            return {"status": "failed", "error": "Invalid dataset"}
        
        lora_path = str(Path(settings.LORA_STORAGE_DIR) / f"{user_id}.safetensors")
        success = trainer.train(user_id, dataset_path, lora_path)
        
        if success:
            users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "lora_path": lora_path,
                    "training_status": TrainingStatus.COMPLETED.value,
                    "updated_at": datetime.utcnow()
                }}
            )
            return {"status": "completed", "lora_path": lora_path}
        else:
            users.update_one(
                {"user_id": user_id},
                {"$set": {"training_status": TrainingStatus.FAILED.value, "updated_at": datetime.utcnow()}}
            )
            return {"status": "failed", "error": "Training failed"}
    
    except Exception as e:
        users.update_one(
            {"user_id": user_id},
            {"$set": {"training_status": TrainingStatus.FAILED.value, "updated_at": datetime.utcnow()}}
        )
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name="generate_tts_task", bind=True, max_retries=2)
def generate_tts_task(self, job_id: str, script_text: str, voice_id: Optional[str]):
    """
    Generate TTS audio from script
    
    Args:
        job_id: Job ID
        script_text: Script text
        voice_id: Optional custom voice ID
        
    Returns:
        Path to generated audio file
    """
    try:
        voice_manager = VoiceManager()
        audio_path = voice_manager.generate_audio(script_text, voice_id, job_id)
        
        if not audio_path:
            raise Exception("TTS generation failed")
        
        return audio_path
    except Exception as e:
        raise self.retry(exc=e, countdown=5)


@celery_app.task(name="generate_talking_head_task", bind=True, max_retries=2)
def generate_talking_head_task(self, job_id: str, user_id: str, audio_path: str):
    """
    Generate talking head video
    
    Args:
        job_id: Job ID
        user_id: User ID
        audio_path: Path to audio file
        
    Returns:
        Path to generated video
    """
    try:
        # Get best face image
        preprocessor = FacePreprocessor()
        face_image_path = preprocessor.get_best_face_image(user_id)
        
        if not face_image_path:
            raise Exception("No face image found for user")
        
        # Generate talking head video
        sadtalker = SadTalkerWrapper()
        video_path = sadtalker.generate_video(
            image_path=face_image_path,
            audio_path=audio_path,
            output_path=str(Path(settings.VIDEO_RAW_DIR) / f"{job_id}.mp4"),
            resolution=getattr(settings, 'SADTALKER_RESOLUTION', 512)
        )
        
        if not video_path:
            raise Exception("Talking head generation failed")
        
        return video_path
    except Exception as e:
        raise self.retry(exc=e, countdown=10)


@celery_app.task(name="compose_product_task", bind=True, max_retries=2)
def compose_product_task(self, video_path: str, product_image_path: Optional[str]):
    """
    Compose video with product image if provided
    
    Args:
        video_path: Path to avatar video
        product_image_path: Optional path to product image
        
    Returns:
        Path to composed video
    """
    if not product_image_path:
        return video_path
    
    try:
        compositor = ProductCompositor()
        composed_path = compositor.process_with_product(
            avatar_video_path=video_path,
            product_image_path=product_image_path,
            remove_bg=True
        )
        
        return composed_path or video_path
    except Exception as e:
        print(f"Product composition failed: {e}")
        return video_path  # Return original video if composition fails


@celery_app.task(name="enhance_video_task", bind=True, max_retries=1)
def enhance_video_task(self, video_path: str, job_id: str):
    """
    Enhance video: face restoration, upscaling, smoothing, color correction
    
    Args:
        video_path: Path to input video
        job_id: Job ID
        
    Returns:
        Path to enhanced video
    """
    try:
        current_video = video_path
        
        # Face restoration
        face_restorer = FaceRestorer()
        restored_path = face_restorer.restore_video(current_video)
        if restored_path and restored_path != current_video:
            current_video = restored_path
        
        # Upscale to 720p
        upscaler = VideoUpscaler()
        upscaled_path = upscaler.upscale_to_resolution(
            current_video,
            settings.VIDEO_TARGET_RESOLUTION
        )
        if upscaled_path and upscaled_path != current_video:
            current_video = upscaled_path
        
        # Temporal smoothing
        smoother = TemporalSmoother()
        smoothed_path = smoother.smooth_video(current_video)
        if smoothed_path and smoothed_path != current_video:
            current_video = smoothed_path
        
        # Color correction
        color_corrector = ColorCorrector()
        final_path = color_corrector.correct_video(current_video)
        if final_path and final_path != current_video:
            current_video = final_path
        
        # Move to final location
        final_output_path = str(Path(settings.VIDEO_FINAL_DIR) / f"{job_id}.mp4")
        os.makedirs(settings.VIDEO_FINAL_DIR, exist_ok=True)
        
        if current_video != final_output_path:
            import shutil
            shutil.move(current_video, final_output_path)
        
        return final_output_path
    except Exception as e:
        print(f"Video enhancement failed: {e}")
        return video_path  # Return original if enhancement fails


@celery_app.task(name="upload_to_s3_task", bind=True, max_retries=3)
def upload_to_s3_task(self, video_path: str, job_id: str):
    """
    Upload video to S3 (optional - returns None if S3 not configured)
    
    Args:
        video_path: Path to video file
        job_id: Job ID
        
    Returns:
        S3 URL if successful, None if S3 not configured or upload failed
    """
    try:
        s3_client = S3Client()
        s3_url = s3_client.upload_video(video_path, f"{job_id}.mp4")
        
        # S3 yapılandırılmamışsa veya upload başarısızsa None döner
        if s3_url is None:
            return None
        
        db = get_database()
        db[JOBS_COLLECTION].update_one(
            {"job_id": job_id},
            {"$set": {
                "s3_url": s3_url,
            }}
        )
        
        return s3_url
    except Exception as e:
        # S3 hatası kritik değil, None döndür
        print(f"S3 upload task failed: {e}")
        return None


@celery_app.task(name="generate_video_task", bind=True, max_retries=1)
def generate_video_task(self, job_id: str):
    """
    Main pipeline task: orchestrates entire video generation
    
    Args:
        job_id: Job ID
        
    Returns:
        Dictionary with job status and video URL
    """
    db = get_database()
    jobs = db[JOBS_COLLECTION]
    users = db[USERS_COLLECTION]
    try:
        job = jobs.find_one({"job_id": job_id})
        if not job:
            return {"status": "failed", "error": "Job not found"}
        
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": JobStatus.PROCESSING.value}}
        )
        
        user = users.find_one({"user_id": job["user_id"]})
        if not user:
            jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": JobStatus.FAILED.value, "error_message": "User not found"}}
            )
            return {"status": "failed", "error": "User not found"}
        
        if user.get("training_status") != TrainingStatus.COMPLETED.value:
            jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": JobStatus.FAILED.value, "error_message": "User identity not trained"}}
            )
            return {"status": "failed", "error": "User identity not trained"}
        
        audio_path = generate_tts_task(job_id, job["script_text"], user.get("voice_id"))
        video_path = generate_talking_head_task(job_id, job["user_id"], audio_path)
        
        if job.get("product_image_path"):
            video_path = compose_product_task(video_path, job["product_image_path"])
        
        final_video_path = enhance_video_task(video_path, job_id)
        
        # S3 upload (opsiyonel - yapılandırılmamışsa atla)
        s3_url = None
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.S3_BUCKET_NAME:
            try:
                s3_url = upload_to_s3_task(final_video_path, job_id)
            except Exception as e:
                print(f"S3 upload failed (non-critical): {e}")
                # S3 hatası kritik değil, devam et
        else:
            print("S3 not configured, skipping upload. Video saved locally.")
        
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "video_path": final_video_path,
                "s3_url": s3_url,
                "status": JobStatus.COMPLETED.value,
                "completed_at": datetime.utcnow()
            }}
        )
        
        return {"status": "completed", "video_path": final_video_path, "s3_url": s3_url}
    
    except Exception as e:
        jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": JobStatus.FAILED.value,
                "error_message": str(e)
            }}
        )
        return {"status": "failed", "error": str(e)}
