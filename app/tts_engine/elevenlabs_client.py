"""ElevenLabs API client for TTS generation"""

import os
import time
import requests
from typing import Optional, BinaryIO
from pathlib import Path
from app.config.settings import settings


class ElevenLabsClient:
    """Client for ElevenLabs TTS API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ElevenLabs client
        
        Args:
            api_key: ElevenLabs API key (defaults to settings)
        """
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        if not self.api_key:
            raise ValueError("ElevenLabs API key not provided")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "xi-api-key": self.api_key
        }
    
    def create_custom_voice(
        self,
        name: str,
        voice_file: BinaryIO,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a custom voice from audio sample
        
        Args:
            name: Voice name
            voice_file: Audio file (WAV format recommended)
            description: Optional description
            
        Returns:
            Voice ID if successful, None otherwise
        """
        url = f"{self.base_url}/voices/add"
        
        files = {
            "files": voice_file
        }
        
        data = {
            "name": name,
        }
        
        if description:
            data["description"] = description
        
        try:
            response = requests.post(url, headers=self.headers, files=files, data=data)
            response.raise_for_status()
            
            result = response.json()
            return result.get("voice_id")
        except requests.exceptions.RequestException as e:
            print(f"Failed to create custom voice: {e}")
            return None
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        stability: float = 0.6,
        similarity_boost: float = 0.8,
        style: float = 0.0,
        output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate speech from text using specified voice
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use
            stability: Stability parameter (0.0-1.0)
            similarity_boost: Similarity boost parameter (0.0-1.0)
            style: Style parameter (0.0-1.0)
            output_path: Path to save audio file
            
        Returns:
            Path to saved audio file if successful, None otherwise
        """
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # Supports Turkish
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            # Save audio to file
            if output_path is None:
                output_path = f"/tmp/tts_{int(time.time())}.wav"
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return output_path
        except requests.exceptions.RequestException as e:
            print(f"Failed to generate speech: {e}")
            return None
    
    def generate_speech_with_retry(
        self,
        text: str,
        voice_id: str,
        output_path: Optional[str] = None,
        retry_attempts: int = None,
        retry_delay: int = None
    ) -> Optional[str]:
        """
        Generate speech with retry logic and fallback to default Turkish voice
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use
            output_path: Path to save audio file
            retry_attempts: Number of retry attempts (defaults to settings)
            retry_delay: Delay between retries in seconds (defaults to settings)
            
        Returns:
            Path to saved audio file if successful, None otherwise
        """
        retry_attempts = retry_attempts or settings.ELEVENLABS_RETRY_ATTEMPTS
        retry_delay = retry_delay or settings.ELEVENLABS_RETRY_DELAY
        
        # Try with custom voice
        for attempt in range(retry_attempts + 1):
            result = self.generate_speech(
                text=text,
                voice_id=voice_id,
                output_path=output_path
            )
            
            if result:
                return result
            
            if attempt < retry_attempts:
                time.sleep(retry_delay)
        
        # Fallback to default Turkish voice
        print(f"Falling back to default Turkish voice after {retry_attempts} attempts")
        return self.generate_speech(
            text=text,
            voice_id=settings.ELEVENLABS_DEFAULT_TURKISH_VOICE_ID,
            output_path=output_path
        )
    
    def list_voices(self) -> list:
        """
        List all available voices
        
        Returns:
            List of voice dictionaries
        """
        url = f"{self.base_url}/voices"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("voices", [])
        except requests.exceptions.RequestException as e:
            print(f"Failed to list voices: {e}")
            return []
