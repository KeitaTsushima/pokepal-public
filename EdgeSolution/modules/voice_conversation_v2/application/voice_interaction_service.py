"""
Service implementing voice interaction use cases
Manages the loop of voice input → conversation processing → voice output
"""
import logging
import time
from typing import Optional

from domain.audio_interfaces import AudioCaptureProtocol, SpeechToTextProtocol, AudioOutputProtocol
from .conversation_service import ConversationService


class VoiceInteractionService:
    """Application service that manages voice interactions"""
    
    def __init__(self, 
                 conversation_service: ConversationService,
                 audio_capture: AudioCaptureProtocol,
                 speech_to_text: SpeechToTextProtocol,
                 audio_output: AudioOutputProtocol,
                 no_voice_sleep_threshold: int = 5):  # TODO: Change to retrieve from defaults.json
        """
        Initialize
        
        Args:
            conversation_service: Conversation processing service
            audio_capture: Audio capture interface
            speech_to_text: Speech recognition interface
            audio_output: Audio output interface (text-to-speech)
            no_voice_sleep_threshold: Threshold for entering sleep mode on silence (#TODO: Planned to retrieve from ConfigLoader)
        """
        self.conversation_service = conversation_service
        self.audio_capture = audio_capture
        self.speech_to_text = speech_to_text
        self.audio_output = audio_output
        
        self.logger = logging.getLogger(__name__)
        
        self.running = True
        self.no_voice_count = 0
        
        self.no_voice_sleep_threshold = no_voice_sleep_threshold
    
    def initialize(self) -> None:
        self.logger.info("Initializing voice interaction service")
        # TODO: Change to retrieve greeting message from configuration
        greeting = "こんにちは！ポケパル音声対話システムが起動しました。"
        self.audio_output.text_to_speech(greeting)
    
    def run(self) -> None:
        self.logger.info("Starting voice interaction loop")
        
        try:
            while self.running:
                try:
                    self.process_conversation()
                except KeyboardInterrupt:
                    self.logger.info("Keyboard interrupt detected")
                    self.stop()
                    break
                except Exception as e:
                    self.logger.error(f"Error occurred during conversation processing: {e}", exc_info=True)
                    time.sleep(1)
        finally:
            self.logger.info("Ending voice interaction loop")
    
    def process_conversation(self) -> None:
        """Process one cycle of voice input → recognition → conversation → voice output"""
        self.logger.debug("Waiting for voice input...")
        audio_file = self.audio_capture.capture_audio()
        if not audio_file:
            self._handle_no_voice()
            return
        
        # Reset silence count (for sleep detection)
        self.no_voice_count = 0
        
        try:
            user_text = self.speech_to_text.transcribe(audio_file)
            if not user_text:
                return
        except Exception as e:
            self.logger.error(f"Speech recognition error: {e}")
            return
        finally:
            self._cleanup_audio_file(audio_file)
        
        if self.conversation_service.conversation.is_sleeping():
            self.conversation_service.conversation.exit_sleep()
        
        if self.conversation_service.is_exit_command(user_text):
            self._announce_farewell(user_text)
            return
        
        ai_response = self.conversation_service.handle_user_input(user_text)
        if not ai_response:
            return
        
        self.audio_output.text_to_speech(ai_response)
    
    def _announce_farewell(self, user_text: str) -> None:
        farewell_message = self.conversation_service.handle_exit_command(user_text)
        
        self.audio_output.text_to_speech(farewell_message)
    
    def _handle_no_voice(self) -> None:
        self.no_voice_count += 1
        self.logger.debug(f"Silence count: {self.no_voice_count}")
        
        if (self.no_voice_count >= self.no_voice_sleep_threshold and 
            not self.conversation_service.conversation.is_sleeping()):
            # TODO: Consider hardware/UI indication (LED dimming, robot gesture, etc.) in separate modules
            # Voice announcement removed as it may interrupt user's intentional silence
            self.conversation_service.conversation.enter_sleep()
            self.logger.debug("Entered sleep mode due to prolonged silence")
        
        time.sleep(0.1)
    
    def stop(self) -> None:
        self.logger.info("Stopping voice interaction service")
        self.running = False
        
        try:
            self.conversation_service.end_session()
        except Exception as e:
            self.logger.error(f"Error during conversation session termination: {e}")
        
        self._cleanup_resources()
    
    def _cleanup_resources(self) -> None:
        try:
            if hasattr(self.audio_capture, 'cleanup'):
                self.audio_capture.cleanup()
            
            if hasattr(self.speech_to_text, 'cleanup'):
                self.speech_to_text.cleanup()
            
            if hasattr(self.audio_output, 'cleanup'):
                self.audio_output.cleanup()
                
            self.logger.info("Resource cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during resource cleanup: {e}")
    
    def _cleanup_audio_file(self, audio_file: str) -> None:
        try:
            import os
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
                self.logger.debug(f"Deleted audio file: {audio_file}")
        except OSError as e:
            self.logger.warning(f"Audio file deletion error: {e}")
    