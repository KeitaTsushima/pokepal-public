"""
Service implementing voice interaction use cases
Manages the loop of voice input → conversation processing → voice output
"""
import asyncio
import logging
import time
from typing import Optional

from domain.audio_interfaces import AudioCaptureProtocol, SpeechToTextProtocol, AudioOutputProtocol
from domain.conversation import MessageRole
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
        
    
    async def initialize(self) -> None:
        self.logger.info("Initializing voice interaction service")
        # TODO: Change to retrieve greeting message from configuration
        greeting = "こんにちは！ポケパル音声対話システムが起動しました。"
        await self.audio_output.speech_announcement(greeting)
        
        # Wait for greeting TTS completion and prevent click noise (stability improvement)
        await asyncio.sleep(0.4)
        self.logger.debug("Initialization greeting completed, system ready for voice input")
    
    async def run(self) -> None:
        self.logger.info("Starting voice interaction loop")
        
        try:
            while self.running:
                try:
                    await self.process_conversation()
                except KeyboardInterrupt:
                    self.logger.info("Keyboard interrupt detected")
                    self.stop()
                    break
                except Exception as e:
                    self.logger.error(f"Error occurred during conversation processing: {e}", exc_info=True)
                    await asyncio.sleep(1)
        finally:
            self.logger.info("Ending voice interaction loop")
    
    async def process_conversation(self) -> None:
        """Process one cycle of voice input → recognition → conversation → voice output"""
        self.logger.debug("Waiting for voice input...")
        audio_file = self.audio_capture.capture_audio()
        if not audio_file:
            self._handle_no_voice()
            return
        
        # Barge-in support: Stop current TTS when user starts speaking
        self.audio_output.stop_audio_for_barge_in()
        
        # Reset silence count (for sleep detection)
        self.no_voice_count = 0
        
        try:
            self.logger.info("STT processing start")
            stt_start = time.monotonic()
            
            # Application-level timeout for STT processing (120s as per expert recommendation)
            user_text = await asyncio.wait_for(
                self.speech_to_text.transcribe(audio_file),
                timeout=120.0
            )
            
            stt_duration = time.monotonic() - stt_start
            self.logger.info("[perf] STT processing completed: %.3fs, result_length=%d chars", 
                           stt_duration, len(user_text) if user_text else 0)
            if not user_text:
                return
        except asyncio.TimeoutError:
            self.logger.error("[perf] STT processing TIMEOUT after 120.000s - async architecture working correctly")
            return
        except Exception as e:
            self.logger.error(f"[perf] STT processing ERROR after %.3fs: {e}", time.monotonic() - stt_start)
            return
        finally:
            self._cleanup_audio_file(audio_file)
        
        if self.conversation_service.conversation.is_sleeping():
            self.conversation_service.conversation.exit_sleep()
        
        if self.conversation_service.is_exit_command(user_text):
            await self._announce_farewell(user_text)
            return
        
        self.logger.info("LLM streaming processing start")
        llm_start = time.monotonic()
        first_segment_time = None
        segment_count = 0
        total_chars_processed = 0
        streaming_session_started = False
        
        # Record user input for telemetry (moved from ConversationService)
        self.conversation_service._record_and_send_utterance(MessageRole.USER.value, user_text)
        
        # Process AI response stream
        try:
            async for ev in self.conversation_service.generate_response_stream(user_text):
                if ev["type"] == "segment":
                    segment_count += 1
                    segment_chars = len(ev["text"])
                    total_chars_processed += segment_chars
                    
                    if first_segment_time is None:
                        first_segment_time = time.monotonic() - llm_start
                        self.logger.info("[perf] LLM first segment ready (TTFT: %.3fs, chars=%d)", 
                                       first_segment_time, segment_chars)
                    
                    # Start streaming session only once for all segments
                    if not streaming_session_started:
                        streaming_session_started = self.audio_output.start_streaming_session()
                        if not streaming_session_started:
                            self.logger.error("Failed to start TTS streaming session")
                            continue
                    
                    # Enhanced TTS segment protection to prevent loop termination
                    try:
                        self.logger.debug("TTS segment #%d processing start", segment_count)
                        tts_start = time.monotonic()
                        
                        # Stream segment to existing session
                        await asyncio.wait_for(
                            self.audio_output.speech_segment_streaming(ev["text"]),
                            timeout=30.0
                        )
                        
                        tts_duration = time.monotonic() - tts_start
                        self.logger.debug("[perf] TTS segment #%d completed: %.3fs, chars=%d", 
                                        segment_count, tts_duration, segment_chars)
                    except asyncio.TimeoutError:
                        self.logger.error("[perf] TTS segment #%d TIMEOUT after 30.000s (chars=%d)", 
                                        segment_count, segment_chars)
                    except Exception as e:
                        # Continue processing even if individual TTS segment fails
                        self.logger.warning(f"[perf] TTS segment #%d ERROR after %.3fs: {e}", 
                                          segment_count, time.monotonic() - tts_start)
                elif ev["type"] == "final":
                    final_text = ev["text"]
                    total_llm_duration = time.monotonic() - llm_start
                    self.logger.info("[perf] LLM streaming completed: %.3fs, total_chars=%d, segments=%d, chars/s=%.1f", 
                                   total_llm_duration, len(final_text), segment_count,
                                   len(final_text) / total_llm_duration if total_llm_duration > 0 else 0)
                elif ev["type"] == "error":
                    error_time = time.monotonic() - llm_start
                    self.logger.error("[perf] LLM streaming ERROR after %.3fs: %s", error_time, ev["text"])
                    # Still try to output the error message via TTS for user feedback
                    try:
                        await asyncio.wait_for(
                            self.audio_output.speech_announcement(ev["text"]),
                            timeout=30.0
                        )
                    except asyncio.TimeoutError:
                        self.logger.error("[perf] Error announcement TIMEOUT after 30.000s")
                    except Exception as e:
                        self.logger.error(f"[perf] Error announcement FAILED: {e}")
        finally:
            # Ensure streaming session is properly closed
            if streaming_session_started:
                await self.audio_output.stop_streaming_session()
                self.logger.info("[perf] TTS streaming session closed")
    
    async def _announce_farewell(self, user_text: str) -> None:
        farewell_message = self.conversation_service.handle_exit_command(user_text)
        
        await self.audio_output.speech_announcement(farewell_message)
    
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
    