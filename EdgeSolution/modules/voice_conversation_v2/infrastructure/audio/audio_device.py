"""
Audio Device Management
Microphone and speaker device control for audio playback
"""
import asyncio
import subprocess
import logging
import tempfile
import os
import threading
import queue
from typing import Dict, Any, List, Optional


class AudioDevice:
    """Audio device management class for speaker and microphone control"""
    
    def __init__(self, config_loader):
        """
        Initialize audio device manager
        
        Args:
            config_loader: ConfigLoader instance for accessing audio configuration
        """
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        # Load device configuration
        self.speaker_device = config_loader.get('audio.speaker_device')
        self.mic_device = config_loader.get('audio.mic_device')
        self.volume = config_loader.get('audio.volume')
        self.sample_rate = config_loader.get('audio.sample_rate')
        
        # Streaming playback state
        self._streaming_process: Optional[subprocess.Popen] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_queue: Optional[queue.Queue] = None
        self._stream_lock = threading.Lock()

        # Async playback state (for barge-in support)
        self._playback_process: Optional[subprocess.Popen] = None
        self._playback_lock = threading.Lock()
        
        self.logger.info("Audio device initialized: speaker=%s, mic=%s", self.speaker_device, self.mic_device)
    
    def play_file(self, file_path: str) -> bool:
        """
        Play audio file through speaker

        Args:
            file_path: Path to audio file to play

        Returns:
            True if playback succeeded, False otherwise
        """
        adjusted_file = None

        try:
            # Apply volume adjustment if needed
            if self.volume != 1.0:
                adjusted_file = self._adjust_volume(file_path)
                if adjusted_file:
                    file_path = adjusted_file
                else:
                    self.logger.warning("Volume adjustment failed. Playing original file.")

            # Use the configured device directly
            cmd = ['aplay', '-D', self.speaker_device, file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.debug("Audio playback successful: %s", self.speaker_device)
                return True
            else:
                self.logger.error("Audio playback failed (%s): %s", self.speaker_device, result.stderr)
                return False

        except Exception as e:
            self.logger.error("Audio playback error (%s): %s", self.speaker_device, e)
            return False

        finally:
            if adjusted_file and os.path.exists(adjusted_file):
                try:
                    os.remove(adjusted_file)
                except OSError:
                    pass

    async def play_file_async(self, file_path: str) -> bool:
        """
        Play audio file asynchronously for barge-in support.

        Wraps blocking aplay subprocess in asyncio.to_thread() to enable
        concurrent VAD monitoring during playback. Can be stopped via stop().

        Args:
            file_path: Path to audio file to play

        Returns:
            True if playback succeeded, False otherwise
        """
        return await asyncio.to_thread(self._play_file_blocking, file_path)

    def _play_file_blocking(self, file_path: str) -> bool:
        """
        Internal blocking playback with process tracking for barge-in.

        Args:
            file_path: Path to audio file to play

        Returns:
            True if playback succeeded, False otherwise
        """
        adjusted_file = None

        try:
            # Apply volume adjustment if needed
            if self.volume != 1.0:
                adjusted_file = self._adjust_volume(file_path)
                if adjusted_file:
                    file_path = adjusted_file
                else:
                    self.logger.warning("Volume adjustment failed. Playing original file.")

            cmd = ['aplay', '-D', self.speaker_device, file_path]

            with self._playback_lock:
                self._playback_process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
                )

            # Wait for playback to complete
            _, stderr = self._playback_process.communicate()
            returncode = self._playback_process.returncode

            with self._playback_lock:
                self._playback_process = None

            if returncode == 0:
                self.logger.debug("Async audio playback successful: %s", self.speaker_device)
                return True
            elif returncode == -15:  # SIGTERM - stopped by stop()
                self.logger.debug("Audio playback stopped by barge-in")
                return False
            else:
                self.logger.error("Async audio playback failed (%s): %s",
                                  self.speaker_device, stderr.decode('utf-8', errors='ignore'))
                return False

        except Exception as e:
            self.logger.error("Async audio playback error (%s): %s", self.speaker_device, e)
            with self._playback_lock:
                self._playback_process = None
            return False

        finally:
            if adjusted_file and os.path.exists(adjusted_file):
                try:
                    os.remove(adjusted_file)
                except OSError:
                    pass

    def play_bytes(self, audio_data: bytes) -> bool:
        """
        Play raw audio data directly (for real-time streaming)
        
        Args:
            audio_data: Raw audio data bytes (PCM/WAV format)
            
        Returns:
            True if playback succeeded, False otherwise
        """
        try:
            # For streaming, audio data should be sent to the streaming process
            if self._streaming_process and self._stream_queue:
                try:
                    # Wait up to 0.5 seconds for queue space
                    # This ensures audio continuity and prevents dropping chunks
                    self._stream_queue.put(audio_data, timeout=0.5)
                    return True
                except queue.Full:
                    # Queue still full after timeout - likely a processing issue
                    self.logger.error("Stream queue full after 0.5s timeout - audio processing may be stalled")
                    return False
            else:
                # Fallback: single chunk playback (not ideal for streaming)
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    tmp_file.write(audio_data)
                    tmp_filename = tmp_file.name
                
                success = self.play_file(tmp_filename)
                
                try:
                    os.unlink(tmp_filename)
                except OSError:
                    pass
                
                return success
            
        except Exception as e:
            self.logger.error("Raw audio data playback error: %s", e)
            return False
    
    def start_streaming_playback(self) -> bool:
        """
        Start a streaming playback session for continuous audio
        
        Returns:
            True if streaming session started successfully
        """
        with self._stream_lock:
            if self._streaming_process:
                self.logger.warning("Streaming session already active")
                return False
            
            try:
                # Create queue for audio chunks
                self._stream_queue = queue.Queue(maxsize=100)
                
                # Start aplay process with stdin pipe for continuous streaming
                # Note: Azure Speech SDK outputs WAV format (RIFF header + PCM data)
                # We'll handle WAV headers in the feeder thread
                # Use 'default' if plughw causes dmix errors
                device = self.speaker_device
                if 'plughw' in device:
                    # Try using default device for better compatibility with dmix
                    device = 'default'
                    self.logger.info("Using 'default' device instead of %s for streaming to avoid dmix issues", self.speaker_device)
                cmd = ['aplay', '-D', device, '-q']  # -q: quiet mode (no console output)
                self._streaming_process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE  # Capture stderr for debugging
                )
                
                # Start feeder thread
                self._stream_thread = threading.Thread(target=self._stream_feeder, daemon=True)
                self._stream_thread.start()
                
                self.logger.info("Streaming playback session started")
                return True
                
            except Exception as e:
                self.logger.error("Failed to start streaming playback: %s", e)
                self._cleanup_streaming()
                return False
    
    def _stream_feeder(self):
        """Feed audio chunks from queue to aplay process"""
        try:
            first_chunk = True
            while self._streaming_process and self._streaming_process.stdin:
                try:
                    # Get chunk from queue with timeout
                    chunk = self._stream_queue.get(timeout=5.0)
                    
                    if chunk is None:  # Sentinel value to stop streaming
                        break
                    
                    # Azure Speech SDK provides complete WAV chunks
                    # For the first chunk, we need the WAV header for format info
                    # For subsequent chunks, we skip headers to avoid audio glitches
                    if first_chunk:
                        # First chunk: send complete WAV data (header + PCM)
                        # aplay needs the header to know the audio format
                        first_chunk = False
                        self.logger.debug("Sending first audio chunk with WAV header (size=%d)", len(chunk))
                    else:
                        # Subsequent chunks: skip WAV header if present
                        if len(chunk) > 44 and chunk[:4] == b'RIFF':
                            # Extract PCM data after WAV header (typically 44 bytes)
                            original_size = len(chunk)
                            chunk = chunk[44:]
                            self.logger.debug("Skipped WAV header: %d -> %d bytes", original_size, len(chunk))
                    
                    # Write audio data to aplay stdin
                    if self._streaming_process and self._streaming_process.stdin:
                        try:
                            self._streaming_process.stdin.write(chunk)
                            self._streaming_process.stdin.flush()
                        except BrokenPipeError:
                            self.logger.warning("Pipe broken during write, stopping stream")
                            break
                        
                except queue.Empty:
                    # Timeout - check if process still alive
                    if self._streaming_process.poll() is not None:
                        self.logger.info("Streaming process terminated")
                        break
                except BrokenPipeError:
                    self.logger.warning("Streaming pipe broken")
                    break
                except Exception as e:
                    self.logger.error("Stream feeder error: %s", e)
                    break
                    
        finally:
            self.logger.debug("Stream feeder thread ending")
    
    def stop_streaming_playback(self):
        """
        Stop the streaming playback session
        """
        with self._stream_lock:
            if self._stream_queue:
                # Send sentinel to stop feeder thread
                try:
                    self._stream_queue.put_nowait(None)
                except queue.Full:
                    pass
            
            # Wait for feeder thread to finish processing remaining data
            if self._stream_thread and self._stream_thread.is_alive():
                self._stream_thread.join(timeout=2.0)
            
            # Wait for aplay to finish playing buffered audio
            if self._streaming_process and self._streaming_process.poll() is None:
                # Close stdin to signal EOF to aplay
                if self._streaming_process.stdin:
                    self._streaming_process.stdin.close()
                # Wait for aplay to finish
                self._streaming_process.wait(timeout=3.0)
            
            self._cleanup_streaming()
            self.logger.info("Streaming playback session stopped")
    
    def _cleanup_streaming(self):
        """Clean up streaming resources"""
        if self._streaming_process:
            try:
                # Check for any stderr output before closing
                if self._streaming_process.stderr:
                    try:
                        stderr_output = self._streaming_process.stderr.read()
                        if stderr_output:
                            self.logger.warning("aplay stderr: %s", stderr_output.decode('utf-8', errors='ignore'))
                    except:
                        pass
                
                if self._streaming_process.stdin:
                    self._streaming_process.stdin.close()
                self._streaming_process.terminate()
                self._streaming_process.wait(timeout=2.0)
            except Exception as e:
                self.logger.debug("Error terminating streaming process: %s", e)
                try:
                    self._streaming_process.kill()
                except Exception:
                    pass
            finally:
                self._streaming_process = None
        
        self._stream_queue = None
        self._stream_thread = None
    
    def _adjust_volume(self, audio_file: str) -> str:
        """
        Create volume-adjusted audio file using sox
        
        Args:
            audio_file: Original audio file path
            
        Returns:
            Path to adjusted file, or None if failed
        """
        adjusted_file = audio_file.replace('.wav', '_adjusted.wav')
        
        try:
            sox_cmd = [
                'sox', audio_file, adjusted_file,
                'vol', str(self.volume)
            ]
            result = subprocess.run(sox_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return adjusted_file
            else:
                self.logger.warning("Sox volume adjustment error: %s", result.stderr)
                return None
                
        except Exception as e:
            self.logger.warning("Sox volume adjustment error: %s", e)
            return None
    
    
    def stop(self) -> None:
        """
        Stop current audio playback for barge-in support.
        Terminates tracked playback process and streaming playback.
        """
        try:
            # Stop the tracked playback process
            with self._playback_lock:
                if self._playback_process and self._playback_process.poll() is None:
                    self._playback_process.terminate()
                    try:
                        self._playback_process.wait(timeout=0.5)
                        self.logger.debug("Tracked playback process terminated")
                    except subprocess.TimeoutExpired:
                        self._playback_process.kill()
                        self._playback_process.wait(timeout=0.5)
                        self.logger.debug("Tracked playback process killed")
                    self._playback_process = None

            # Stop streaming if active
            self.stop_streaming_playback()

            self.logger.debug("Audio playback stopped")
        except Exception as e:
            self.logger.debug("Error stopping audio playback: %s", e)
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        Update audio device configuration
        
        Args:
            new_config: New configuration values to update
        """
        for key, value in new_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.debug("Updated audio config: %s = %s", key, value)
        
    def cleanup(self) -> None:
        """Cleanup audio device resources"""
        try:
            self.stop()  # Stop any ongoing playback
            self.stop_streaming_playback()  # Ensure streaming is stopped
            self.logger.info("AudioDevice cleanup completed")
        except Exception as e:
            self.logger.error("AudioDevice cleanup error: %s", e)