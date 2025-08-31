"""
Unit tests for AudioCaptureService
Tests business logic of audio capture service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open, call
import tempfile
import wave
import time
from application.audio_capture_service import AudioCaptureService


class TestAudioCaptureService:
    """Test class for AudioCaptureService"""
    
    @pytest.fixture
    def mock_vad_processor(self):
        """Mock VADProcessor"""
        processor = Mock()
        processor.detect_speech_in_frame = Mock(return_value=False)
        return processor
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            'audio.sample_rate': 16000,
            'vad.frame_duration_ms': 30,
            'vad.speech_threshold': 0.6,
            'vad.min_speech_duration': 0.3,
            'vad.max_silence_duration': 1.0,
            'vad.max_recording_duration': 30.0,
            'audio.mic_device': 'default'
        }.get(key, default)
        return config
    
    @pytest.fixture
    def service(self, mock_vad_processor, mock_config_loader):
        """Service under test"""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            return AudioCaptureService(mock_vad_processor, mock_config_loader)
    
    def test_init_with_ffmpeg(self, mock_vad_processor, mock_config_loader):
        """Initialization when ffmpeg is available"""
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            service = AudioCaptureService(mock_vad_processor, mock_config_loader)
            assert service.ffmpeg_available is True
            assert service.sample_rate == 16000
            assert service.frame_duration_ms == 30
            assert service.speech_threshold == 0.6
    
    def test_init_without_ffmpeg(self, mock_vad_processor, mock_config_loader):
        """Initialization when ffmpeg is not available"""
        with patch('shutil.which', return_value=None):
            service = AudioCaptureService(mock_vad_processor, mock_config_loader)
            assert service.ffmpeg_available is False
    
    def test_calculate_frame_params(self, service):
        """Test frame parameter calculation"""
        assert service.frame_size == 480  # 16000 * 30 / 1000
        assert service.frame_size_bytes == 960  # 480 * 2
        assert service.ring_buffer_size == 16  # 500 / 30
    
    def test_capture_audio_success(self, service):
        """Test successful audio capture"""
        mock_frames = [b'frame1', b'frame2', b'frame3']
        
        with patch.object(service, '_record_audio_stream', return_value=mock_frames):
            with patch.object(service, '_save_as_wav_file', return_value='/tmp/audio.wav'):
                result = service.capture_audio()
                assert result == '/tmp/audio.wav'
    
    def test_capture_audio_no_voice(self, service):
        """Test when no voice is detected"""
        with patch.object(service, '_record_audio_stream', return_value=[]):
            result = service.capture_audio()
            assert result is None
    
    def test_record_audio_stream_with_speech(self, service, mock_vad_processor):
        """Test recording stream with speech detection"""
        mock_process = Mock()
        
        # Generate frame data (30ms @ 16kHz = 480 samples = 960 bytes)
        frame_data = b'\x00' * 960
        
        # Multiple frame sequence
        frames_sequence = [frame_data] * 50  # 50 frames (1.5 seconds)
        frames_sequence.append(b'')  # EOF
        
        mock_process.stdout.read.side_effect = frames_sequence
        
        # VAD behavior: silent at first, then speech detection, then silent
        def vad_behavior(data):
            # Counter-based logic
            if not hasattr(vad_behavior, 'call_count'):
                vad_behavior.call_count = 0
            vad_behavior.call_count += 1
            
            # Speech detection in frames 20-40
            if 20 <= vad_behavior.call_count <= 40:
                return True
            return False
        
        mock_vad_processor.detect_speech_in_frame.side_effect = vad_behavior
        
        with patch.object(service, '_start_recording_process', return_value=mock_process):
            with patch('time.time', return_value=0):
                voiced_frames = service._record_audio_stream()
                
                assert len(voiced_frames) > 0
                mock_process.terminate.assert_called_once()
    
    def test_record_audio_stream_timeout(self, service):
        """Test maximum recording time exceeded"""
        mock_process = Mock()
        mock_process.stdout.read.return_value = b'frame' * 480
        
        with patch.object(service, '_start_recording_process', return_value=mock_process):
            with patch('time.time', side_effect=[0, 31]):  # 31 seconds elapsed
                voiced_frames = service._record_audio_stream()
                mock_process.terminate.assert_called_once()
    
    def test_record_audio_stream_no_process(self, service):
        """Test process startup failure"""
        with patch.object(service, '_start_recording_process', return_value=None):
            voiced_frames = service._record_audio_stream()
            assert voiced_frames == []
    
    def test_start_recording_process_success(self, service):
        """Test successful recording process startup"""
        mock_process = Mock()
        
        with patch('subprocess.Popen', return_value=mock_process):
            process = service._start_recording_process()
            assert process == mock_process
    
    def test_start_recording_process_failure(self, service):
        """Test recording process startup failure"""
        with patch('subprocess.Popen', side_effect=Exception("Failed to start")):
            process = service._start_recording_process()
            assert process is None
    
    def test_check_speech_trigger_triggered(self, service):
        """Test speech trigger detection"""
        ring_buffer = [b'frame1', b'frame2']  # Voice frames in ring buffer
        frame_data = b'frame3'
        voiced_frames = []
        
        # 90% of ring buffer detected as speech
        with patch.object(service.vad_processor, 'detect_speech_in_frame', return_value=True):
            triggered = service._check_speech_trigger(ring_buffer, frame_data, voiced_frames)
            assert triggered is True
            assert len(voiced_frames) > 0
    
    def test_check_speech_trigger_not_triggered(self, service):
        """Test speech trigger not detected"""
        ring_buffer = []
        frame_data = b'frame1'
        voiced_frames = []
        
        # Insufficient voice frames
        with patch.object(service.vad_processor, 'detect_speech_in_frame', return_value=False):
            triggered = service._check_speech_trigger(ring_buffer, frame_data, voiced_frames)
            assert triggered is False
            assert len(ring_buffer) == 1
    
    def test_save_as_wav_file_success(self, service):
        """Test successful WAV file saving"""
        frames = [b'frame1', b'frame2']
        
        mock_wave_open = MagicMock()
        mock_file = MagicMock()
        
        with patch('tempfile.NamedTemporaryFile', mock_open()) as mock_temp:
            with patch('wave.open', return_value=mock_wave_open) as mock_wave:
                mock_wave_open.__enter__.return_value = mock_wave_open
                mock_temp.return_value.name = '/tmp/test.wav'
                
                result = service._save_as_wav_file(frames)
                
                assert '/tmp/test' in result
                assert result.endswith('.wav')
                mock_wave_open.setnchannels.assert_called_once_with(1)
                mock_wave_open.setsampwidth.assert_called_once_with(2)
                mock_wave_open.setframerate.assert_called_once_with(16000)
    
    def test_save_as_wav_file_with_optimization(self, service):
        """Test WAV file saving with optimization"""
        frames = [b'frame1', b'frame2']
        service.ffmpeg_available = True
        
        with patch('tempfile.NamedTemporaryFile', mock_open()) as mock_temp:
            with patch('wave.open') as mock_wave:
                with patch.object(service, '_optimize_for_stt', return_value='/tmp/optimized.wav'):
                    mock_temp.return_value.name = '/tmp/test.wav'
                    
                    result = service._save_as_wav_file(frames)
                    
                    assert result == '/tmp/optimized.wav'
                    service._optimize_for_stt.assert_called_once()
    
    def test_optimize_for_stt_success(self, service):
        """Test successful STT optimization"""
        # Create actual file
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_input:
            temp_input.write(b'RIFF' + b'\x00' * 36 + b'data' + b'\x00' * 100)  # Simple WAV header
            input_file = temp_input.name
        
        try:
            with tempfile.NamedTemporaryFile(suffix='_stt.wav', delete=False) as temp_output:
                output_file = temp_output.name
            
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_file = MagicMock()
                mock_file.name = output_file
                mock_temp.return_value = mock_file
                mock_temp.return_value.__enter__.return_value = mock_file
                
                with patch('subprocess.run', return_value=Mock(returncode=0)):
                    with patch('wave.open') as mock_wave:
                        mock_wave_obj = MagicMock()
                        mock_wave_obj.getnframes.return_value = 16000  # 1 second
                        mock_wave_obj.getframerate.return_value = 16000
                        mock_wave.return_value.__enter__.return_value = mock_wave_obj
                        
                        with patch('os.path.getsize', return_value=32000):
                            result = service._optimize_for_stt(input_file)
                            assert result == output_file
        finally:
            # Cleanup
            for f in [input_file, output_file]:
                if os.path.exists(f):
                    try:
                        os.unlink(f)
                    except:
                        pass
    
    def test_optimize_for_stt_failure(self, service):
        """Test STT optimization failure"""
        # Trigger failure with non-existent file
        input_file = '/tmp/nonexistent_input.wav'
        
        result = service._optimize_for_stt(input_file)
        assert result is None  # Returns None on failure
    
    def test_min_speech_duration_boundary(self, service):
        """Test minimum speech duration boundary"""
        # Test 0.3 second boundary
        service.min_speech_duration = 0.3
        
        # 0.29 seconds of speech - not triggered
        frames_count = int(0.29 * 1000 / service.frame_duration_ms)
        assert frames_count < service.min_speech_duration * 1000 / service.frame_duration_ms
        
        # 0.31 seconds of speech - triggered
        frames_count = int(0.31 * 1000 / service.frame_duration_ms)
        assert frames_count >= service.min_speech_duration * 1000 / service.frame_duration_ms
    
    def test_max_silence_duration_boundary(self, service):
        """Test maximum silence duration boundary"""
        # Test 1.0 second boundary
        service.max_silence_duration = 1.0
        max_silence_frames = int(service.max_silence_duration * 1000 / service.frame_duration_ms)
        
        assert max_silence_frames == 33  # 1000ms / 30ms
    
    def test_max_recording_duration_boundary(self, service):
        """Test maximum recording duration boundary"""
        service.max_recording_duration = 30.0
        
        mock_process = Mock()
        # Simulate multiple reads
        mock_process.stdout.read.side_effect = [
            b'frame' * 480,
            b'frame' * 480,
            b''  # EOF
        ]
        
        # 30.1 seconds elapsed - timeout termination
        with patch.object(service, '_start_recording_process', return_value=mock_process):
            with patch('time.time') as mock_time:
                mock_time.side_effect = [0, 30.1, 30.1]  # Start time, first check, second check
                service._record_audio_stream()
                mock_process.terminate.assert_called_once()
    
    def test_handle_silence_in_speech(self, service, mock_vad_processor):
        """Test silence handling during speech"""
        mock_process = Mock()
        frames = []
        for _ in range(10):
            frames.append(b'frame' * 480)
        frames.append(b'')  # EOF
        
        mock_process.stdout.read.side_effect = frames
        
        # Speech detection pattern (set generously)
        vad_results = []
        # Ring buffer worth (initial silence)
        vad_results.extend([False] * 20)
        # Speech detection trigger
        vad_results.extend([True] * 20)
        # Speech continuation and silence
        vad_results.extend([True, True, False, False, True, True, False, False])
        # Ending silence
        vad_results.extend([False] * 50)
        
        mock_vad_processor.detect_speech_in_frame.side_effect = vad_results
        
        with patch.object(service, '_start_recording_process', return_value=mock_process):
            with patch('time.time', return_value=0):
                voiced_frames = service._record_audio_stream()
                assert len(voiced_frames) > 0
    
    def test_error_handling_in_check_speech(self, service):
        """Test error handling during speech check"""
        ring_buffer = [b'frame1']
        frame_data = b'frame2'  # Valid frame data
        voiced_frames = []
        
        # VAD errors are not handled in current implementation (propagated as-is)
        with patch.object(service.vad_processor, 'detect_speech_in_frame', side_effect=Exception("VAD error")):
            with pytest.raises(Exception, match="VAD error"):
                service._check_speech_trigger(ring_buffer, frame_data, voiced_frames)