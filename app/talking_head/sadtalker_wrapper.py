"""SadTalker wrapper for talking head video generation"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
from app.config.settings import settings


class SadTalkerWrapper:
    """Wrapper for SadTalker inference"""
    
    def __init__(self, sadtalker_path: Optional[str] = None):
        """
        Initialize SadTalker wrapper
        
        Args:
            sadtalker_path: Path to SadTalker repository (optional)
        """
        # Use settings if available, otherwise fallback to environment variable or default
        if sadtalker_path:
            self.sadtalker_path = sadtalker_path
        else:
            # Try settings first, then environment variable, then default
            self.sadtalker_path = getattr(settings, 'SADTALKER_PATH', None) or \
                                 os.getenv("SADTALKER_PATH", "/workspace/SadTalker")
        
        # Resolve to absolute path
        self.sadtalker_path = os.path.abspath(os.path.expanduser(self.sadtalker_path))
        
        # Same for checkpoint path
        self.checkpoint_path = getattr(settings, 'SADTALKER_CHECKPOINT_PATH', None) or \
                             os.getenv("SADTALKER_CHECKPOINT_PATH", "/workspace/SadTalker/checkpoints")
        self.checkpoint_path = os.path.abspath(os.path.expanduser(self.checkpoint_path))
    
    def generate_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: Optional[str] = None,
        resolution: int = 512
    ) -> Optional[str]:
        """
        Generate talking head video from image and audio
        
        Args:
            image_path: Path to reference face image (512x512)
            audio_path: Path to audio WAV file
            output_path: Output video path (optional)
            resolution: Output resolution (default 512)
            
        Returns:
            Path to generated video if successful, None otherwise
        """
        if output_path is None:
            output_path = str(Path(settings.VIDEO_RAW_DIR) / f"{Path(audio_path).stem}.mp4")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Check if SadTalker is available
        if not self._check_sadtalker_available():
            # Fallback: use subprocess call if SadTalker is installed separately
            return self._generate_via_subprocess(image_path, audio_path, output_path, resolution)
        
        # Use Python API if available
        return self._generate_via_api(image_path, audio_path, output_path, resolution)
    
    def _check_sadtalker_available(self) -> bool:
        """Check if SadTalker is available as Python module"""
        try:
            # Try importing SadTalker
            import sys
            sys.path.insert(0, self.sadtalker_path)
            # This would work if SadTalker is properly installed
            return False  # For now, use subprocess approach
        except ImportError:
            return False
    
    def _patch_sadtalker_numpy_compatibility(self):
        """
        Patches the SadTalker my_awing_arch.py file to replace deprecated np.float with np.float64.
        This is necessary due to NumPy 1.20+ deprecating np.float.
        """
        target_file = os.path.join(self.sadtalker_path, "src", "face3d", "util", "my_awing_arch.py")
        
        if not os.path.exists(target_file):
            print(f"Warning: SadTalker patch target file not found: {target_file}", file=sys.stderr)
            return
        
        try:
            # Read the file
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already patched
            if 'np.float64' in content and 'np.float' not in content:
                return  # Already patched
            
            # Replace np.float with np.float64
            original_content = content
            content = content.replace('np.float', 'np.float64')
            
            # Only write if there was a change
            if content != original_content:
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Patched: {target_file} - replaced np.float with np.float64", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to patch SadTalker NumPy compatibility: {e}", file=sys.stderr)
    
    def _patch_sadtalker_preprocess(self):
        """
        Patches the SadTalker preprocess.py to fix inhomogeneous array error.
        NumPy 2.x is stricter about np.array with mixed scalar/array elements.
        """
        target_file = os.path.join(self.sadtalker_path, "src", "face3d", "util", "preprocess.py")
        
        if not os.path.exists(target_file):
            print(f"Warning: SadTalker preprocess patch target not found: {target_file}", file=sys.stderr)
            return
        
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already patched
            if '_to_scalar' in content or 'np.asarray(t[0]).flat[0]' in content:
                return  # Already patched
            
            old_line = "trans_params = np.array([w0, h0, s, t[0], t[1]])"
            new_line = "trans_params = np.array([float(w0), float(h0), float(s), float(np.asarray(t[0]).flat[0]), float(np.asarray(t[1]).flat[0])], dtype=np.float64)"
            
            if old_line in content:
                content = content.replace(old_line, new_line)
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Patched: {target_file} - fixed trans_params inhomogeneous array", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to patch SadTalker preprocess: {e}", file=sys.stderr)
    
    def _generate_via_subprocess(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        resolution: int
    ) -> Optional[str]:
        """
        Generate video via SadTalker subprocess call
        
        Args:
            image_path: Path to reference image
            audio_path: Path to audio file
            output_path: Output video path
            resolution: Output resolution
            
        Returns:
            Output path if successful, None otherwise
        """
        # Apply SadTalker compatibility patches before running the subprocess
        self._patch_sadtalker_numpy_compatibility()
        self._patch_sadtalker_preprocess()
        
        # SadTalker inference script path
        inference_script = os.path.join(self.sadtalker_path, "inference.py")
        
        if not os.path.exists(inference_script):
            # Try alternative paths
            inference_script = os.path.join(self.sadtalker_path, "inference", "inference.py")
        
        if not os.path.exists(inference_script):
            print(f"SadTalker inference script not found at {inference_script}", file=sys.stderr)
            print("Please ensure SadTalker is installed and SADTALKER_PATH is set correctly")
            return None
        
        cmd = [
            sys.executable,
            inference_script,
            "--driven_audio", audio_path,
            "--source_image", image_path,
            "--result_dir", os.path.dirname(output_path),
            "--checkpoint_dir", self.checkpoint_path,
            "--preprocess", "full",  # Full preprocessing
            "--enhancer", "gfpgan",  # Use GFPGAN for enhancement
            "--background_enhancer", "realesrgan",  # Background enhancement
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.sadtalker_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # SadTalker typically outputs to a timestamped directory
            # Find the generated video file
            output_dir = Path(os.path.dirname(output_path))
            video_files = list(output_dir.glob("*.mp4"))
            
            if video_files:
                # Copy/rename to desired output path
                generated_video = video_files[0]
                if str(generated_video) != output_path:
                    import shutil
                    shutil.copy2(generated_video, output_path)
                
                return output_path
            
            return None
        except subprocess.CalledProcessError as e:
            print(f"SadTalker inference failed: {e.stderr}", file=sys.stderr)
            return None
    
    def _generate_via_api(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        resolution: int
    ) -> Optional[str]:
        """
        Generate video via SadTalker Python API
        
        Args:
            image_path: Path to reference image
            audio_path: Path to audio file
            output_path: Output video path
            resolution: Output resolution
            
        Returns:
            Output path if successful, None otherwise
        """
        # Placeholder for direct Python API integration
        # In production, integrate with SadTalker's Python API directly
        # This would involve:
        # 1. Loading the model
        # 2. Processing the image and audio
        # 3. Generating frames
        # 4. Combining into video
        
        print("Direct Python API integration not yet implemented")
        return None
    
    def validate_inputs(self, image_path: str, audio_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate input files
        
        Args:
            image_path: Path to image file
            audio_path: Path to audio file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(image_path):
            return False, f"Image file not found: {image_path}"
        
        if not os.path.exists(audio_path):
            return False, f"Audio file not found: {audio_path}"
        
        # Check image format
        valid_image_extensions = ['.jpg', '.jpeg', '.png']
        if not any(image_path.lower().endswith(ext) for ext in valid_image_extensions):
            return False, f"Invalid image format. Supported: {valid_image_extensions}"
        
        # Check audio format
        if not audio_path.lower().endswith('.wav'):
            return False, "Audio file must be in WAV format"
        
        return True, None
