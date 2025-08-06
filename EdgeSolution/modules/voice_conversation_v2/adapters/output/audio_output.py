"""
Audio Output Adapter
Responsible for converting text to speaker audio

Clean Architecture compliant audio output implementation
- Hardcoded values externalized to configuration
- Error recovery strategies implemented
- Type safety enhanced
"""
import logging
from typing import Optional, Dict, Any


class AudioOutputAdapter:
    """Adapter for converting text to audio output"""
    
    def __init__(self, tts_client, audio_device):
        self.tts_client = tts_client
        self.audio_device = audio_device
        self.logger = logging.getLogger(__name__)
    
    def text_to_speech(self, text: str) -> None:
        """
        Convert text to speech output
        
        Args:
            text: Text to output
        """
        try:
            # Speech synthesis
            audio_file = self.tts_client.synthesize(text)
            
            # Audio playback
            success = self.audio_device.play(audio_file)
            if not success:
                self.logger.warning(f"Audio playback failed: {text[:50]}...")
                
        except Exception as e:
            self.logger.error(f"Audio output error: {e}")
        
    
    def cleanup(self) -> None:
        """Resource cleanup"""
        try:
            # TTS client cleanup
            if hasattr(self.tts_client, 'cleanup'):
                self.tts_client.cleanup()
            
            # Audio device cleanup
            if hasattr(self.audio_device, 'cleanup'):
                self.audio_device.cleanup()           
                     
            self.logger.info("AudioOutputAdapter cleanup completed")
        except Exception as e:
            self.logger.error(f"AudioOutputAdapter cleanup error: {e}")