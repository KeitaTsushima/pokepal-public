#!/usr/bin/env python3
"""
Audio Interfaces - Protocol definitions for audio processing
Defines abstractions for audio input/output in the Domain layer
"""
from typing import Protocol, Optional, Dict, Any


class AudioCaptureProtocol(Protocol):
    """Abstract interface for audio capture"""
    
    def capture_audio(self) -> Optional[str]:
        """
        Returns:
            Audio file path, or None if no audio detected
        """
        ...
    
    def cleanup(self) -> None:
        ...


class SpeechToTextProtocol(Protocol):
    """Abstract interface for speech-to-text conversion"""
    
    def transcribe(self, audio_file: str) -> Optional[str]:
        """
        Args:
            audio_file: Path to the audio file
            
        Returns:
            Recognized text, or None if recognition failed
        """
        ...
    
    def update_config(self, config: Dict[str, Any]) -> None:
        ...
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        ...
    
    def cleanup(self) -> None:
        ...


class AudioOutputProtocol(Protocol):
    """Abstract interface for audio output"""
    
    def text_to_speech(self, text: str) -> None:
        ...
    
    def stop_audio_for_barge_in(self) -> None:
        ...
    
    def cleanup(self) -> None:
        ...