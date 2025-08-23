"""
VAD Processor
Voice Activity Detection implementation using WebRTC VAD
"""
import logging
from typing import Optional
import webrtcvad


class VADProcessor:
    """Voice Activity Detection using WebRTC VAD algorithm"""
    
    def __init__(self, sample_rate: int = 16000, vad_mode: int = 2):
        """
        Initialize VAD processor
        
        Args:
            sample_rate: Audio sample rate in Hz (8000, 16000, 32000, 48000)
            vad_mode: VAD aggressiveness mode (0-3, 3 is most aggressive)
        """
        self.logger = logging.getLogger(__name__)
        self.sample_rate = sample_rate
        self.vad_mode = vad_mode
        
        # Validate parameters
        self._validate_parameters()
        
        # Initialize WebRTC VAD
        try:
            self.vad = webrtcvad.Vad(self.vad_mode)
            self.logger.info("VAD processor initialized (mode=%d, sample_rate=%d)", self.vad_mode, self.sample_rate)
        except Exception as e:
            self.logger.error("Failed to initialize WebRTC VAD: %s", e)
            raise
    
    def detect_speech_in_frame(self, audio_frame: bytes) -> bool:
        """
        Detect speech/silence in a single audio frame
        
        Args:
            audio_frame: Audio frame data (PCM bytes)
            
        Returns:
            True if speech is detected, False for silence
        """
        try:
            return self.vad.is_speech(audio_frame, self.sample_rate)
        except Exception as e:
            self.logger.error("VAD speech detection failed: %s", e)
            return False  # Conservative fallback: assume silence
    
    def _validate_parameters(self) -> None:
        """Validate initialization parameters"""
        valid_sample_rates = [8000, 16000, 32000, 48000]
        if self.sample_rate not in valid_sample_rates:
            raise ValueError(f"Invalid sample rate {self.sample_rate}. Must be one of {valid_sample_rates}")
            
        if not (0 <= self.vad_mode <= 3):
            raise ValueError(f"Invalid VAD mode {self.vad_mode}. Must be between 0 and 3")
