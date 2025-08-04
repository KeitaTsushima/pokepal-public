"""
Audio Capture Service
Records audio using VADProcessor with business logic-based control
"""
import subprocess
import wave
import time
import tempfile
import logging
from typing import Optional, List


class AudioCaptureService:
    """Service that manages business logic for audio capture"""
    
    def __init__(self, vad_processor, config_loader):
        self.vad_processor = vad_processor
        self.config_loader = config_loader
        self.logger = logging.getLogger(__name__)
        
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
        self.audio_device = self.config_loader.get('audio.mic_device', 'plughw:3,0')
    
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
                else:
                    voiced_frames.append(frame_data)
                    silence_frames = self._update_silence_counter(is_speech, silence_frames)
                    
                    if silence_frames > max_silence_frames:
                        self.logger.info("End of speech detected")
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
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.wav', delete=False) as f:
            output_file = f.name
            
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(voiced_frames))
        
        speech_duration = len(voiced_frames) * self.frame_duration_ms / 1000
        self.logger.info(f"Recording complete: {output_file} ({speech_duration:.1f}s)")
        return output_file
    
    def cleanup(self) -> None:
        self.logger.info("AudioCaptureService cleanup completed")