"""
Azure Speech Core Synthesizer
Core Azure Speech SDK functionality with connection management
"""
import os
import logging
import threading
import time
import queue
from typing import Optional, Dict, Any, List, Iterator
from xml.sax.saxutils import escape

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

from infrastructure.security.key_vault_client import KeyVaultClient


class TTSCoreSynthesizer:
    """Core Azure Speech TTS functionality with connection pre-establishment"""
    
    UPDATABLE_FIELDS = ['voice_name', 'speech_rate', 'speech_pitch']
    
    def __init__(self, config_loader):
        """
        Args:
            config_loader: ConfigLoader instance for dynamic configuration access
        
        Environment Variables:
            AZURE_SPEECH_KEY: Azure Speech Service subscription key (required)
        """
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        if speechsdk is None:
            raise ImportError("Azure Speech SDK not available. Install with: pip install azure-cognitiveservices-speech")
        
        # Store secret name for on-demand Key Vault access
        self.speech_secret_name = os.environ['AZURE_SPEECH_SECRET_NAME']
        
        self.region = self.config_loader.get('tts.region')
        self.voice_name = self.config_loader.get('tts.voice_name')
        self.speech_rate = max(0.5, min(2.0, self.config_loader.get('tts.speech_rate')))
        self.speech_pitch = max(-50, min(50, self.config_loader.get('tts.speech_pitch')))
        
        # Fast temp path (RAM disk). Fallback to current directory if not available
        self._tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else "."
        
        self._initialize_synthesizer()
        self._initialize_connection()
        
        # Real-time streaming lock for automatic interruption
        self._rt_lock = threading.Lock()
        # Current epoch for generation management (prevents old callback interference)
        self._current_epoch = None
        
        # Warm-up connection in background (Microsoft best practice)
        threading.Thread(target=self._warmup, daemon=True).start()
        
        self.logger.info("Azure Speech Core Synthesizer initialized with voice: %s", self.voice_name)
    
    def _initialize_synthesizer(self) -> None:
        try:
            # Get Azure Speech key from Key Vault on-demand
            key_vault_client = KeyVaultClient()
            subscription_key = key_vault_client.get_secret(self.speech_secret_name)
            
            self.speech_config = speechsdk.SpeechConfig(
                subscription=subscription_key,
                region=self.region
            )
            
            self.speech_config.speech_synthesis_voice_name = self.voice_name
            # Use PCM format for direct audio device playback (Raspberry Pi compatibility)
            self.speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            
            self.logger.info(f"Using temp directory: {self._tmp_dir}")
            
        except Exception as e:
            self.logger.error("Failed to initialize Azure Speech synthesizer: %s", e)
            raise
    
    def _initialize_connection(self) -> None:
        """Initialize pre-connection for reduced latency (Microsoft best practice)"""
        try:
            # Create synthesizer without audio output config (for connection pre-establishment only)
            self.synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config
            )
            
            # Pre-establish connection for faster first synthesis
            self.connection = speechsdk.Connection.from_speech_synthesizer(self.synthesizer)
            self.connection.open(True)
            
            self.logger.info("Azure Speech connection pre-established")
            
        except Exception as e:
            self.logger.error("Failed to initialize connection: %s", e)
            self.synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config
            )
            self.connection = None
    
    def _warmup(self) -> None:
        """Warm-up connection with tiny synthesis to hide TLS/WebSocket setup cost"""
        try:
            ssml = self.create_ssml("。")
            # use the pre-established synthesizer and disabled speaker
            fut = self.synthesizer.start_speaking_ssml_async(ssml)
            fut.get()
            self.logger.info("TTS warm-up completed")
        except Exception as e:
            self.logger.debug(f"Warm-up skipped ({e})")
    
    def create_ssml(self, text: str, speech_rate: Optional[float] = None) -> str:
        # XML escape to prevent SSML corruption from user input
        safe_text = escape(text, {'"': '&quot;', "'": '&apos;'})
        
        rate = speech_rate if speech_rate is not None else self.speech_rate
        
        # Guard speech parameters against abnormal values
        safe_rate = float(max(0.5, min(2.0, rate)))
        safe_pitch = int(max(-50, min(50, self.speech_pitch)))
        
        rate_percent = f"{(safe_rate - 1.0) * 100:+.0f}%"
        pitch_percent = f"{safe_pitch:+.0f}%"
        
        ssml = f'''
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ja-JP">
            <voice name="{self.voice_name}">
                <prosody rate="{rate_percent}" pitch="{pitch_percent}">
                    {safe_text}
                </prosody>
            </voice>
        </speak>
        '''.strip()
        
        return ssml
    
    def synthesize_basic(self, text: str, output_file: str, speech_rate: Optional[float] = None) -> Optional[str]:
        try:
            ssml = self.create_ssml(text, speech_rate)
            
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=audio_config
            )
            
            result = self._speak_with_retry(synthesizer, ssml)
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self._log_latency_properties(result)
                return output_file
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                self.logger.error("Synthesis canceled: %s", cancellation.reason)
                if cancellation.error_details:
                    self.logger.error("Cancellation error details: %s", cancellation.error_details)
                return None
            else:
                self.logger.error("Synthesis failed: %s", result.reason)
                return None
                
        except Exception as e:
            self.logger.error("Synthesis error: %s", e)
            return None
    
    def _speak_with_retry(self, synthesizer, ssml, tries=2):
        delay = 0.4
        for t in range(tries):
            result = synthesizer.speak_ssml_async(ssml).get()
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result
            if result.reason == speechsdk.ResultReason.Canceled and t + 1 < tries:
                self.logger.warning(f"TTS synthesis failed, retrying in {delay}s (attempt {t+1}/{tries})")
                time.sleep(delay)
                delay *= 2
                continue
            return result
    
    def _log_latency_properties(self, result) -> None:
        try:
            props = result.properties
            def gp(pid):
                try:
                    v = props.get_property(pid)
                    return v if v is not None else "N/A"
                except Exception:
                    return "N/A"

            first  = gp(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs)
            finish = gp(speechsdk.PropertyId.SpeechServiceResponse_SynthesisFinishLatencyMs)
            net    = gp(speechsdk.PropertyId.SpeechServiceResponse_SynthesisNetworkLatencyMs)
            svc    = gp(speechsdk.PropertyId.SpeechServiceResponse_SynthesisServiceLatencyMs)
            self.logger.info(
                f"Azure Speech latency metrics: FirstByte={first}ms, Finish={finish}ms, "
                f"Network={net}ms, Service={svc}ms"
            )
        except Exception as e:
            self.logger.debug(f"Failed to log latency properties: {e}")
    
    def update_config(self) -> None:
        updated_fields = self._update_field_values()
        if 'voice_name' in updated_fields:
            self._reinitialize_synthesizer()
    
    def _update_field_values(self) -> List[str]:
        updated_fields = []
        
        for field in self.UPDATABLE_FIELDS:
            config_key = f'tts.{field}'
            new_value = self.config_loader.get(config_key)
            
            if new_value is not None:
                validated_value = self._validate_field_value(field, new_value)
                
                current_value = getattr(self, field)
                if current_value != validated_value:
                    setattr(self, field, validated_value)
                    self.logger.info("Updated %s: %s", field, validated_value)
                    updated_fields.append(field)
        
        return updated_fields
    
    def _validate_field_value(self, field: str, value: Any) -> Any:
        if field == 'speech_rate':
            return max(0.5, min(2.0, value))
        elif field == 'speech_pitch':
            return max(-50, min(50, value))
        else:
            return value
    
    def _reinitialize_synthesizer(self) -> None:
        try:
            if getattr(self, 'connection', None):
                try:
                    self.connection.close()
                except Exception:
                    pass
            
            self._initialize_synthesizer()
            self._initialize_connection()
            
            threading.Thread(target=self._warmup, daemon=True).start()
            
            self.logger.info("Synthesizer reinitialized with new voice: %s", self.voice_name)
        except Exception as e:
            self.logger.error("Failed to reinitialize synthesizer: %s", e)
    
    def synthesize_streaming_realtime(self, text: str) -> Iterator[bytes]:
        """
        Real-time streaming synthesis with automatic interruption
        Yields audio chunks (bytes) as they arrive for immediate playback
        """
        epoch = self._acquire_lock_with_interruption()
        
        try:
            yield from self._execute_streaming_synthesis(text, epoch)
        finally:
            self._cleanup_session(epoch)
    
    def _acquire_lock_with_interruption(self) -> int:
        """Acquire lock with automatic interruption and return epoch"""
        # Non-blocking lock acquisition with automatic interruption
        if not self._rt_lock.acquire(blocking=False):
            # Lock busy - interrupt previous stream and try again with timeout
            self.stop_realtime()
            if not self._rt_lock.acquire(timeout=2.0):
                raise RuntimeError("TTS stream busy - could not acquire lock within 2 seconds")
        
        # Generate epoch for this session to prevent old callback interference
        epoch = time.monotonic_ns()
        self._current_epoch = epoch
        return epoch
    
    def _execute_streaming_synthesis(self, text: str, epoch: int) -> Iterator[bytes]:
        """Execute the main streaming synthesis logic"""
        q: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=64)
        synthesizer = self.synthesizer
        
        # Setup event handlers with epoch checking
        on_synth, on_completed, on_canceled = self._create_event_handlers(q, epoch)
        
        # Connect event handlers
        synthesizer.synthesizing.connect(on_synth)
        synthesizer.synthesis_completed.connect(on_completed)
        synthesizer.synthesis_canceled.connect(on_canceled)
        
        try:
            # Start synthesis
            ssml = self.create_ssml(text)
            fut = synthesizer.start_speaking_ssml_async(ssml)
            threading.Thread(target=lambda: fut.get(), daemon=True).start()
            
            # Yield chunks with timeout protection
            yield from self._yield_chunks_with_timeout(q)
            
        finally:
            # Disconnect event handlers
            self._disconnect_event_handlers(synthesizer, on_synth, on_completed, on_canceled)
    
    def _create_event_handlers(self, q: queue.Queue, epoch: int):
        """Create event handlers with epoch checking"""
        def on_synth(e):
            # Check epoch to prevent old callback interference
            if getattr(self, '_current_epoch', None) != epoch:
                return
            try:
                data = e.result.audio_data  # type: ignore[attr-defined]
                if data:
                    try:
                        q.put_nowait(bytes(data))
                    except queue.Full:
                        # Replace oldest chunk with newest (real-time priority)
                        try:
                            q.get_nowait()  # Remove oldest chunk
                            q.put_nowait(bytes(data))  # Add new chunk
                        except queue.Empty:
                            pass  # Race condition: another thread already consumed
            except Exception as e:
                self.logger.debug(f"Audio chunk processing failed: {e}")
        
        def on_completed(e):
            # Check epoch to prevent old callback interference
            if getattr(self, '_current_epoch', None) != epoch:
                return
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
        
        def on_canceled(e):
            # Check epoch to prevent old callback interference  
            if getattr(self, '_current_epoch', None) != epoch:
                return
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
        
        return on_synth, on_completed, on_canceled
    
    def _yield_chunks_with_timeout(self, q: queue.Queue) -> Iterator[bytes]:
        """Yield audio chunks with timeout protection"""
        SILENCE_TIMEOUT_SEC = int(self.config_loader.get("synthesis.silence_timeout_sec"))
        
        try:
            while True:
                try:
                    chunk = q.get(timeout=SILENCE_TIMEOUT_SEC)
                except queue.Empty:
                    # Timeout occurred - stop synthesis and raise error
                    self._stop_synthesis_non_blocking()
                    raise TimeoutError(f"TTS synthesis timeout after {SILENCE_TIMEOUT_SEC} seconds")
                
                if chunk is None:
                    break
                
                yield chunk
                
        except GeneratorExit:
            # Caller abandoned generator early (e.g., barge-in) - stop synthesis
            self._stop_synthesis_non_blocking()
            raise  # Re-raise GeneratorExit to maintain proper cleanup
    
    def _disconnect_event_handlers(self, synthesizer, on_synth, on_completed, on_canceled):
        """Safely disconnect event handlers"""
        try:
            if synthesizer:
                if hasattr(synthesizer, "synthesizing"):
                    synthesizer.synthesizing.disconnect(on_synth)
                if hasattr(synthesizer, "synthesis_completed"):
                    synthesizer.synthesis_completed.disconnect(on_completed)
                if hasattr(synthesizer, "synthesis_canceled"):
                    synthesizer.synthesis_canceled.disconnect(on_canceled)
        except Exception as e:
            self.logger.debug(f"Event handler disconnect failed: {e}")
    
    def _cleanup_session(self, epoch: int):
        """Clean up session resources"""
        # Clear epoch if it matches current session
        if getattr(self, '_current_epoch', None) == epoch:
            self._current_epoch = None
        self._rt_lock.release()
    
    
    def _stop_synthesis_non_blocking(self) -> None:
        """Stop synthesis with non-blocking timeout (1.5sec max wait)"""
        try:
            fut = self.synthesizer.stop_speaking_async()
            t = threading.Thread(target=lambda: fut.get(), daemon=True)
            t.start()
            t.join(timeout=1.5)
        except Exception as e:
            self.logger.warning(f"TTS stop failed (non-critical): {e}")
    
    def stop_realtime(self) -> None:
        """Stop real-time synthesis (useful for barge-in)"""
        try:
            self.synthesizer.stop_speaking_async().get()
        except Exception as e:
            self.logger.error("Failed to stop real-time synthesis: %s", e)
    
    def cleanup(self) -> None:
        try:
            if hasattr(self, 'connection') and self.connection:
                try:
                    self.connection.close()
                    self.logger.info("Azure Speech connection closed")
                except Exception as e:
                    self.logger.warning("Failed to close connection: %s", e)
            
            self.logger.info("Azure Speech Core Synthesizer cleanup completed")
        except Exception as e:
            self.logger.error("Azure Speech Core Synthesizer cleanup error: %s", e)
    
    @property
    def tmp_dir(self) -> str:
        return self._tmp_dir
    