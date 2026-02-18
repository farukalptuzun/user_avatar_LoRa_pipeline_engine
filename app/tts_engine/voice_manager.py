"""Voice management for custom voice creation and storage"""

import os
from typing import Optional
from pathlib import Path
from app.tts_engine.elevenlabs_client import ElevenLabsClient
from app.config.settings import settings


class VoiceManager:
    """Manage custom voices and TTS generation"""
    
    def __init__(self):
        """Initialize voice manager"""
        self.client = ElevenLabsClient()
    
    def create_user_voice(
        self,
        user_id: str,
        voice_sample_path: str
    ) -> Optional[str]:
        """
        Create custom voice for user from voice sample
        
        Args:
            user_id: User ID
            voice_sample_path: Path to voice sample audio file
            
        Returns:
            Voice ID if successful, None otherwise
        """
        voice_name = f"user_{user_id}"
        
        with open(voice_sample_path, "rb") as voice_file:
            voice_id = self.client.create_custom_voice(
                name=voice_name,
                voice_file=voice_file,
                description=f"Custom voice for user {user_id}"
            )
        
        return voice_id
    
    def generate_audio(
        self,
        text: str,
        voice_id: Optional[str],
        job_id: str
    ) -> Optional[str]:
        """
        Generate audio from text using voice_id or default Turkish voice
        
        Args:
            text: Text to convert to speech
            voice_id: Custom voice ID (optional)
            job_id: Job ID for output file naming
            
        Returns:
            Path to generated audio file
        """
        # Validate text length
        if len(text) > settings.SCRIPT_MAX_CHARACTERS:
            raise ValueError(
                f"Script exceeds maximum length of {settings.SCRIPT_MAX_CHARACTERS} characters"
            )
        
        # Determine output path
        output_path = str(Path(settings.AUDIO_DIR) / f"{job_id}.wav")
        os.makedirs(settings.AUDIO_DIR, exist_ok=True)
        
        # Use custom voice if provided, otherwise use default Turkish voice
        target_voice_id = voice_id or settings.ELEVENLABS_DEFAULT_TURKISH_VOICE_ID
        
        # Generate speech with retry logic
        audio_path = self.client.generate_speech_with_retry(
            text=text,
            voice_id=target_voice_id,
            output_path=output_path
        )
        
        return audio_path
    
    def get_default_turkish_voice_id(self) -> str:
        """
        Get default Turkish voice ID
        
        Returns:
            Default Turkish voice ID
        """
        return settings.ELEVENLABS_DEFAULT_TURKISH_VOICE_ID
