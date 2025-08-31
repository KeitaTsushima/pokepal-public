"""
Audio Capture Service
Records audio using VADProcessor with business logic-based control
"""
import subprocess
import wave
import time
import tempfile
import logging
import os
import shutil
from typing import Optional, List


class AudioCaptureService:
    """Service that manages business logic for audio capture"""
    
    def __init__(self, vad_processor, config_loader):
        self.vad_processor = vad_processor
        self.config_loader = config_loader
        self.logger = logging.getLogger(__name__)
        
        # Check ffmpeg availability once at startup for STT optimization
        self.ffmpeg_available = shutil.which("ffmpeg") is not None
        if not self.ffmpeg_available:
            self.logger.warning("ffmpeg not found; STT optimization disabled")
        else:
            self.logger.debug("ffmpeg available; STT optimization enabled")
        
        self._load_config()
        self._calculate_frame_params()
    
    def _load_config(self):
        # TODO: Move hardcoded values to configuration file for better maintainability
        # Current implementation uses embedded defaults, should use external config
        self.sample_rate = self.config_loader.get('audio.sample_rate', 16000)
        self.frame_duration_ms = self.config_loader.get('vad.frame_duration_ms', 30)
        self.speech_threshold = self.config_loader.get('vad.speech_threshold', 0.6)
        self.min_speech_duration = self.config_loader.get('vad.min_speech_duration', 0.3)
        self.max_silence_duration = self.config_loader.get('vad.max_silence_duration', 1.0)
        self.max_recording_duration = self.config_loader.get('vad.max_recording_duration', 30.0)
        self.audio_device = self.config_loader.get('audio.mic_device')
        
        # Log VAD configuration for debugging
        self.logger.info(f"VAD Configuration: speech_threshold={self.speech_threshold}, "
                        f"min_speech_duration={self.min_speech_duration}s, "
                        f"max_silence_duration={self.max_silence_duration}s, "
                        f"max_recording_duration={self.max_recording_duration}s")
    
    def _calculate_frame_params(self):
        self.frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
        self.frame_size_bytes = self.frame_size * 2  # 16-bit audio
        self.ring_buffer_size = int(500 / self.frame_duration_ms)  # 0.5 seconds
    
    def capture_audio(self) -> Optional[str]:
        """
        Wait for voice input and record
        
        Returns:
            Path to recorded audio file, or None if no audio detected
        """
        self.logger.debug(f"Starting audio capture (device: {self.audio_device})")
        
        voiced_frames = self._record_audio_stream()
        if not voiced_frames:
            return None
            
        return self._save_as_wav_file(voiced_frames)
    
    def _record_audio_stream(self) -> List[bytes]:
        voiced_frames = []
        ring_buffer = []
        triggered = False
        silence_frames = 0
        max_silence_frames = int(self.max_silence_duration * 1000 / self.frame_duration_ms)
        
        process = self._start_recording_process()
        if not process:
            return []
            
        start_time = time.time()
        
        try:
            while True:
                frame_data = process.stdout.read(self.frame_size_bytes)
                
                if len(frame_data) < self.frame_size_bytes:
                    break
                
                if time.time() - start_time > self.max_recording_duration:
                    self.logger.info("Maximum recording duration reached")
                    break
                
                is_speech = self.vad_processor.detect_speech_in_frame(frame_data)
                
                if not triggered:
                    triggered = self._check_speech_trigger(ring_buffer, frame_data, voiced_frames)
                    if triggered:
                        self.logger.info("Speech detection start")
                else:
                    voiced_frames.append(frame_data)
                    silence_frames = self._update_silence_counter(is_speech, silence_frames)
                    
                    if silence_frames > max_silence_frames:
                        self.logger.info("Speech detection end")
                        break
        finally:
            process.terminate()
            process.wait()
        
        return self._validate_audio_duration(voiced_frames)
    
    def _start_recording_process(self):
        cmd = [
            'arecord', '-D', self.audio_device, '-f', 'S16_LE',
            '-r', str(self.sample_rate), '-c', '1', '-t', 'raw', '-q', '-'
        ]
        
        try:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            self.logger.error(f"Failed to start recording process: {e}")
            self.logger.error(f"Attempted to use device: {self.audio_device}")
            return None
    
    def _check_speech_trigger(self, ring_buffer: list, frame_data: bytes, voiced_frames: list) -> bool:
        ring_buffer.append(frame_data)
        if len(ring_buffer) > self.ring_buffer_size:
            ring_buffer.pop(0)
        
        num_voiced = sum(1 for f in ring_buffer if self.vad_processor.detect_speech_in_frame(f))
        if num_voiced > self.speech_threshold * len(ring_buffer):
            self.logger.info("Speech detected! Recording...")
            voiced_frames.extend(ring_buffer)
            ring_buffer.clear()
            return True
        return False
    
    def _update_silence_counter(self, is_speech: bool, silence_frames: int) -> int:
        return 0 if is_speech else silence_frames + 1
    
    def _validate_audio_duration(self, voiced_frames: List[bytes]) -> List[bytes]:
        if not voiced_frames:
            self.logger.debug("No speech detected")
            return []
        
        speech_duration = len(voiced_frames) * self.frame_duration_ms / 1000
        if speech_duration < self.min_speech_duration:
            self.logger.debug(f"Speech too short: {speech_duration:.1f}s")
            return []
        
        return voiced_frames
    
    def _save_as_wav_file(self, voiced_frames: List[bytes]) -> str:
        # Create temporary raw file first
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.wav', delete=False) as f:
            raw_output_file = f.name
            
        with wave.open(raw_output_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(voiced_frames))
        
        speech_duration = len(voiced_frames) * self.frame_duration_ms / 1000
        self.logger.info(f"Recording complete: {raw_output_file} ({speech_duration:.1f}s)")
        
        # STT optimization: Apply ffmpeg 16k/mono + silence trimming for faster STT processing
        optimized_file = self._optimize_for_stt(raw_output_file)
        return optimized_file if optimized_file else raw_output_file
    
    def _optimize_for_stt(self, input_file: str) -> Optional[str]:
        """
        Optimize audio file for STT processing using ffmpeg
        - Convert to 16kHz mono (reduces upload size and server processing)
        - Trim silence at end (reduces processing time)
        
        Expected improvement: 300-600ms reduction in STT processing time
        """
        # Early return if ffmpeg not available
        if not self.ffmpeg_available:
            return None
            
        try:
            # Use /dev/shm (RAM disk) if available for faster I/O
            temp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir()
            
            with tempfile.NamedTemporaryFile(mode='wb', suffix='_stt.wav', delete=False, dir=temp_dir) as f:
                optimized_file = f.name
            
            # ffmpeg command: 16kHz mono + silence removal
            cmd = [
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', input_file,
                '-af', 'silenceremove=stop_periods=1:stop_duration=0.4:stop_threshold=-45dB',  # trim end silence
                '-ac', '1',      # mono
                '-ar', '16000',  # 16kHz sample rate
                '-acodec', 'pcm_s16le',
                '-f', 'wav',     # WAV format
                optimized_file
            ]
            
            self.logger.debug(f"STT optimization: {input_file} -> {optimized_file}")
            t0 = time.time()
            # Estimate: input_seconds × 0.3 + 3 seconds (assuming RasPi). Apply upper/lower limits.
            est_timeout = max(6, min(30, int((os.path.getsize(input_file) / (32000)) * 0.3 + 3)))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=est_timeout)
            t1 = time.time()
            
            if result.returncode == 0:
                # Check optimized file duration before using it
                try:
                    with wave.open(optimized_file, 'rb') as wf:
                        duration = wf.getnframes() / wf.getframerate()
                        
                    if duration < 0.1:  # Whisper API minimum
                        self.logger.warning(f"Optimized audio too short: {duration:.2f}s, using original file")
                        os.unlink(optimized_file)
                        return None
                        
                    # Clean up original file
                    try:
                        os.unlink(input_file)
                    except Exception:
                        pass
                    processing_time = t1 - t0
                    self.logger.info(f"STT-optimized audio: {optimized_file} (duration={duration:.2f}s, ffmpeg={processing_time:.2f}s)")
                    return optimized_file
                    
                except Exception as e:
                    self.logger.warning(f"Failed to check optimized audio duration: {e}, using original")
                    try:
                        os.unlink(optimized_file)
                    except Exception:
                        pass
                    return None
            else:
                self.logger.warning(f"ffmpeg optimization failed: {result.stderr}")
                # Clean up failed output file
                try:
                    os.unlink(optimized_file)
                except Exception:
                    pass
                return None
                
        except subprocess.TimeoutExpired:
            self.logger.warning("ffmpeg optimization timeout, using original file")
            return None
        except Exception as e:
            self.logger.warning(f"STT optimization error: {e}, using original file")
            return None
    
    def cleanup(self) -> None:
        self.logger.info("AudioCaptureService cleanup completed")