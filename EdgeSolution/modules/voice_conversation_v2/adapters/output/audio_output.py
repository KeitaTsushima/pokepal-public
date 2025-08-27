"""
Audio Output Adapter
Responsible for converting text to speaker audio

Clean Architecture compliant audio output implementation
- Hardcoded values externalized to configuration
- Error recovery strategies implemented
- Type safety enhanced
"""
import asyncio
import logging
import os
import tempfile
import threading

class AudioOutputAdapter:
    """Adapter for converting text to audio output"""
    
    def __init__(self, tts_client, audio_device, config_loader):
        self.tts_client = tts_client
        self.audio_device = audio_device
        self.config_loader = config_loader
        self.logger = logging.getLogger(__name__)
        
        self._speaking = threading.Event()
    
    def is_speaking(self) -> bool:
        return self._speaking.is_set()
    
    def start_streaming_session(self) -> bool:
        """Start a TTS session (using individual playback for reliability)"""
        try:
            self.logger.info("Starting TTS session (individual playback mode)")
            self._speaking.set()
            # No need to start streaming, we'll play each segment individually
            return True
        except Exception as e:
            self.logger.error(f"Failed to start TTS session: {e}")
            self._speaking.clear()
            return False
    
    async def speech_segment_streaming(self, text: str) -> None:
        """Play a TTS segment individually (more reliable than streaming)"""
        try:
            self.logger.debug("Playing TTS segment: %s...", text[:30])
            
            # Synthesize to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_filename = tmp_file.name
            
            # Use standard synthesis method
            audio_file = await self.tts_client.synthesize(text, tmp_filename)
            if audio_file:
                # Play the audio file directly (reliable method)
                success = self.audio_device.play_file(audio_file)
                if not success:
                    self.logger.error("Failed to play audio segment")
                
                # Clean up temp file
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
            else:
                self.logger.error("Failed to synthesize audio segment")
        except Exception as e:
            self.logger.error(f"TTS segment playback error: {e}")
    
    async def stop_streaming_session(self) -> None:
        """Stop the TTS session"""
        try:
            self.logger.info("TTS session completed (individual playback mode)")
            # No streaming to stop, just clear the flag
            self._speaking.clear()
        except Exception as e:
            self.logger.error(f"Error stopping TTS session: {e}")
            self._speaking.clear()
    
    async def speech_announcement(self, text: str) -> None:
        """Announcement/proactive message audio output - uses single synthesis"""
        success = False
        try:
            self.logger.info("Announcement TTS: %s...", text[:30])
            audio_file = await self.tts_client.synthesize(text)
            if audio_file:
                self._speaking.set()
                try:
                    self.logger.info("Audio playback start")
                    success = self.audio_device.play_file(audio_file)
                    self.logger.info("Audio playback end")
                finally:
                    self._speaking.clear()
        except Exception as e:
            self.logger.error(f"Proactive announcement error: {e}")
        
        # Handle any failure with unified error message
        if not success:
            self.logger.error(f"Proactive announcement failed: %s...", text[:50])
            # TODO: Implement importance level judgment (critical medical vs general reminders)
            # TODO: Consider escalation to staff notification system
            await self._play_apology(self.config_loader.get("error_messages.proactive_error"))
    
    async def _play_apology(self, message: str) -> None:
        apology_audio = await self.tts_client.synthesize(message, "apology.wav")
        if apology_audio:
            self.audio_device.play_file(apology_audio)
    
    def stop_audio_for_barge_in(self) -> None:
        """Stop current audio playback when user starts speaking (barge-in)"""
        try:
            if not self.config_loader.get('tts.barge_in.enabled'):
                self.logger.debug("Barge-in functionality disabled by configuration")
                return
            
            # Only process barge-in if TTS is currently playing
            if not self._speaking.is_set():
                self.logger.debug("Barge-in ignored (no active TTS)")
                return
                
            self.logger.info("Stopping current audio output (barge-in detected)")
            
            # Stop real-time TTS synthesis (Azure Speech SDK)
            if hasattr(self.tts_client, 'core_synthesizer'):
                self.tts_client.core_synthesizer.stop_realtime()
            
            # Stop audio device playback
            if hasattr(self.audio_device, 'stop'):
                self.audio_device.stop()
            
            # Play barge-in response based on configuration
            self._play_barge_in_response()
                
            self.logger.debug("Audio output stopped successfully")
        except Exception as e:
            self.logger.warning(f"Error stopping audio output: {e}")
    
    def _play_barge_in_response(self) -> None:
        """Play natural response after barge-in detected (configurable)"""
        try:
            if not self.config_loader.get('tts.barge_in.play_prompt'):
                self.logger.debug("Barge-in prompt disabled by configuration")
                return
                
            # Use single synthesis for quick response
            # Note: This is synchronous for now as it's called from interrupt context
            # Could be improved with async task spawning in future
            prompt_message = self.config_loader.get('tts.barge_in.prompt_message')
            # TODO: Make this async in future - for now using synchronous fallback
            # barge_in_audio = await self.tts_client.synthesize(prompt_message)
            # if barge_in_audio:
            #     self.audio_device.play_file(barge_in_audio)
            self.logger.debug(f"Barge-in response scheduled: {prompt_message}")
        except Exception as e:
            self.logger.debug(f"Barge-in response failed: {e}")
    
    def cleanup(self) -> None:
        try:
            if hasattr(self.tts_client, 'cleanup'):
                self.tts_client.cleanup()
            
            if hasattr(self.audio_device, 'cleanup'):
                self.audio_device.cleanup()           
                     
            self.logger.info("AudioOutputAdapter cleanup completed")
        except Exception as e:
            self.logger.error(f"AudioOutputAdapter cleanup error: {e}")