"""
TTS File Manager
Temporary file management and cleanup functionality
"""
import os
import time
import glob
import logging
import threading
from typing import Optional


class TTSFileManager:
    """Manages temporary audio files and automatic cleanup"""
    
    def __init__(self, tmp_dir: str):
        """
        Args:
            tmp_dir: Temporary directory path for audio files
        """
        self.logger = logging.getLogger(__name__)
        self.tmp_dir = tmp_dir
        
        self.logger.info("TTS File Manager initialized with temp dir: %s", tmp_dir)
    
    def cleanup_audio_file(self, audio_file: str, delay: float = 2.0) -> None:
        """
        Delete audio file after delay (to ensure playback completion)
        
        Args:
            audio_file: Path to audio file to delete
            delay: Delay in seconds before deletion
        """
        def delayed_cleanup():
            try:
                time.sleep(delay)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                    self.logger.debug("Cleaned up audio file: %s", audio_file)
            except Exception as e:
                self.logger.warning("Failed to cleanup audio file %s: %s", audio_file, e)
        
        # Run cleanup in background thread
        threading.Thread(target=delayed_cleanup, daemon=True).start()
    
    def cleanup_all_temp_files(self) -> None:
        """Clean up all temporary audio files in various locations"""
        try:
            # Clean up any remaining temporary audio files (including /dev/shm)
            temp_files = (
                glob.glob(os.path.join(self.tmp_dir, "stream_part_*.wav")) +
                glob.glob("stream_part_*.wav") +
                glob.glob("response.wav") +
                glob.glob("stream_part_*.mp3") +  # Legacy cleanup
                glob.glob("response.mp3")        # Legacy cleanup
            )
            
            cleaned_count = 0
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.logger.debug("Cleaned up temporary file: %s", file_path)
                        cleaned_count += 1
                except Exception as e:
                    self.logger.warning("Failed to cleanup %s: %s", file_path, e)
            
            if cleaned_count > 0:
                self.logger.info("Cleaned up %d temporary audio files", cleaned_count)
                
        except Exception as e:
            self.logger.error("TTS File Manager cleanup error: %s", e)
    
    def get_temp_file_path(self, prefix: str = "stream_part", suffix: str = ".wav") -> str:
        """
        Generate a unique temporary file path
        
        Args:
            prefix: File name prefix
            suffix: File extension
            
        Returns:
            Full path to temporary file
        """
        ts = int(time.time() * 1000)
        filename = f"{prefix}_{ts}{suffix}"
        return os.path.join(self.tmp_dir, filename)
    
    def calculate_cleanup_delay(self, text: str, speech_rate: float = 1.0) -> float:
        """
        Calculate optimal cleanup delay based on text length and speech rate
        
        Args:
            text: Text content for duration estimation
            speech_rate: Speech rate multiplier
            
        Returns:
            Cleanup delay in seconds
        """
        # Estimate playback duration: 7 chars/sec baseline
        est_playback = len(text) / (7.0 * max(0.6, speech_rate))
        # Add buffer time (minimum 15 seconds, or 2x playback + 5 seconds)
        cleanup_delay = max(15.0, est_playback * 2 + 5)
        
        self.logger.debug(
            "Calculated cleanup delay: %.1fs for %d chars (rate=%.2f)", cleanup_delay, len(text), speech_rate
            )
        
        return cleanup_delay
