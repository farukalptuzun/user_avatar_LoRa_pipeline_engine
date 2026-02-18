"""S3 client for video storage and retrieval"""

import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from datetime import timedelta
from app.config.settings import settings


class S3Client:
    """S3 client for uploading and downloading videos"""
    
    def __init__(self):
        """Initialize S3 client"""
        if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = None
            self.bucket_name = None
        else:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.S3_BUCKET_NAME
    
    def upload_video(self, local_path: str, s3_key: str) -> Optional[str]:
        """
        Upload video file to S3
        
        Args:
            local_path: Path to local video file
            s3_key: S3 object key (filename)
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if not self.s3_client or not self.bucket_name:
            print("S3 not configured, skipping upload")
            return None
        
        if not os.path.exists(local_path):
            print(f"File not found: {local_path}")
            return None
        
        try:
            # Upload file
            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': 'video/mp4',
                    'ACL': 'private'  # Private by default, use presigned URLs
                }
            )
            
            # Return S3 URL
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            return s3_url
        
        except ClientError as e:
            print(f"Failed to upload to S3: {e}")
            return None
    
    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate presigned URL for video download
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default 1 hour)
            
        Returns:
            Presigned URL if successful, None otherwise
        """
        if not self.s3_client or not self.bucket_name:
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Failed to generate presigned URL: {e}")
            return None
    
    def download_video(self, s3_key: str, local_path: str) -> bool:
        """
        Download video from S3
        
        Args:
            s3_key: S3 object key
            local_path: Local path to save video
            
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client or not self.bucket_name:
            return False
        
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            return True
        except ClientError as e:
            print(f"Failed to download from S3: {e}")
            return False
    
    def delete_video(self, s3_key: str) -> bool:
        """
        Delete video from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client or not self.bucket_name:
            return False
        
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            print(f"Failed to delete from S3: {e}")
            return False
    
    def extract_key_from_url(self, s3_url: str) -> Optional[str]:
        """
        Extract S3 key from S3 URL
        
        Args:
            s3_url: S3 URL (s3://bucket/key or https://...)
            
        Returns:
            S3 key if valid, None otherwise
        """
        if s3_url.startswith("s3://"):
            # Format: s3://bucket/key
            parts = s3_url.replace("s3://", "").split("/", 1)
            if len(parts) == 2:
                return parts[1]
        elif "amazonaws.com" in s3_url:
            # Format: https://bucket.s3.region.amazonaws.com/key
            # Extract key from URL
            try:
                from urllib.parse import urlparse
                parsed = urlparse(s3_url)
                key = parsed.path.lstrip("/")
                return key
            except Exception:
                pass
        
        return None
