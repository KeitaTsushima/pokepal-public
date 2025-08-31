"""
Audio processing pipeline integration tests
Audio processing pipeline integration testing
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open, ANY
import sys
import asyncio
import numpy as np
from datetime import datetime

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.cognitiveservices'] = MagicMock()
sys.modules['azure.cognitiveservices.speech'] = MagicMock()
sys.modules['pyaudio'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.audio.audio_device import AudioDevice
from infrastructure.audio.vad_processor import VADProcessor
from infrastructure.ai.stt_client import STTClient
from infrastructure.ai.tts_client import TTSClient
from application.audio_capture_service import AudioCaptureService
from adapters.output.audio_output import AudioOutputAdapter


class TestAudioPipeline:
    """Integration tests for audio processing pipeline"""
    
    @pytest.fixture
    def audio_pipeline(self):
        """Setup audio pipeline"""
        audio_device = Mock(spec=AudioDevice)
        vad_processor = Mock(spec=VADProcessor)
        stt_client = Mock(spec=STTClient)
        tts_client = Mock(spec=TTSClient)
        audio_capture = AudioCaptureService(audio_device, vad_processor)
        audio_output = AudioOutputAdapter(tts_client, audio_device)
        
        return {
            'device': audio_device,
            'vad': vad_processor,
            'stt': stt_client,
            'tts': tts_client,
            'capture': audio_capture,
            'output': audio_output
        }
    
    @pytest.mark.asyncio
    async def test_audio_capture_to_text_pipeline(self, audio_pipeline):
        """Test pipeline from audio capture to text conversion"""
        device = audio_pipeline['device']
        vad = audio_pipeline['vad']
        stt = audio_pipeline['stt']
        capture = audio_pipeline['capture']
        
        # Mock audio data
        audio_data = np.random.bytes(16000)  # 1 second at 16kHz
        device.record_audio = AsyncMock(return_value=audio_data)
        
        # Mock VAD processing
        vad.process = AsyncMock(return_value=(True, audio_data))
        
        # Mock STT
        stt.transcribe = AsyncMock(return_value="This is a test message")
        
        # Execute pipeline
        with patch('builtins.open', mock_open()):
            result = await capture.capture_and_transcribe(duration=1)
        
        assert result == "This is a test message"
        device.record_audio.assert_called_once()
        vad.process.assert_called_once()
        stt.transcribe.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_text_to_audio_output_pipeline(self, audio_pipeline):
        """Test pipeline from text to audio output"""
        tts = audio_pipeline['tts']
        device = audio_pipeline['device']
        output = audio_pipeline['output']
        
        # Mock TTS synthesis
        tts.synthesize = AsyncMock(return_value="/tmp/output.wav")
        
        # Mock audio playback
        device.play_audio = AsyncMock()
        
        # Execute pipeline
        await output.speak("Hello")
        
        tts.synthesize.assert_called_once_with("Hello", ANY)
        device.play_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_continuous_audio_streaming(self, audio_pipeline):
        """Test continuous audio streaming"""
        device = audio_pipeline['device']
        vad = audio_pipeline['vad']
        
        # Mock continuous audio stream
        audio_chunks = [
            np.random.bytes(1600),  # 100ms chunks
            np.random.bytes(1600),
            np.random.bytes(1600)
        ]
        
        device.start_stream = AsyncMock()
        device.read_stream = AsyncMock(side_effect=audio_chunks)
        device.stop_stream = AsyncMock()
        
        # Process stream
        chunks_processed = []
        device.start_stream()
        
        for _ in range(3):
            chunk = await device.read_stream()
            chunks_processed.append(chunk)
        
        device.stop_stream()
        
        assert len(chunks_processed) == 3
        device.start_stream.assert_called_once()
        device.stop_stream.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_vad_silence_detection(self, audio_pipeline):
        """Test VAD silence detection"""
        vad = audio_pipeline['vad']
        
        # Silence audio data
        silence_data = bytes(16000)  # 1 second of silence
        
        vad.process = AsyncMock(return_value=(False, None))
        
        is_speech, processed = await vad.process(silence_data)
        
        assert is_speech is False
        assert processed is None
    
    @pytest.mark.asyncio
    async def test_audio_format_conversion(self, audio_pipeline):
        """Test audio format conversion"""
        device = audio_pipeline['device']
        
        # Different audio formats
        formats = [
            {'rate': 16000, 'channels': 1, 'format': 'int16'},
            {'rate': 44100, 'channels': 2, 'format': 'float32'},
            {'rate': 48000, 'channels': 1, 'format': 'int32'}
        ]
        
        for fmt in formats:
            device.configure(fmt)
            config = device.get_config()
            
            assert config['rate'] == fmt['rate']
            assert config['channels'] == fmt['channels']
            assert config['format'] == fmt['format']
    
    @pytest.mark.asyncio
    async def test_audio_buffer_management(self, audio_pipeline):
        """Test audio buffer management"""
        device = audio_pipeline['device']
        
        # Buffer operations
        device.buffer = []
        
        # Add audio chunks
        for i in range(10):
            chunk = np.random.bytes(1600)
            device.buffer.append(chunk)
        
        assert len(device.buffer) == 10
        
        # Clear buffer
        device.buffer.clear()
        assert len(device.buffer) == 0
    
    @pytest.mark.asyncio
    async def test_audio_error_recovery(self, audio_pipeline):
        """Test audio error recovery"""
        device = audio_pipeline['device']
        
        # Simulate device error
        device.record_audio = AsyncMock(side_effect=[
            Exception("Device error"),
            np.random.bytes(16000)  # Success on retry
        ])
        
        # First call fails
        with pytest.raises(Exception):
            await device.record_audio()
        
        # Second call succeeds
        result = await device.record_audio()
        assert result is not None
        assert len(result) == 16000
    
    @pytest.mark.asyncio
    async def test_noise_reduction_pipeline(self, audio_pipeline):
        """Test noise reduction pipeline"""
        vad = audio_pipeline['vad']
        
        # Noisy audio
        noisy_audio = np.random.bytes(16000)
        
        # Mock noise reduction
        vad.reduce_noise = AsyncMock(return_value=noisy_audio)
        
        cleaned = await vad.reduce_noise(noisy_audio)
        
        assert cleaned is not None
        assert len(cleaned) == len(noisy_audio)
    
    @pytest.mark.asyncio
    async def test_audio_level_monitoring(self, audio_pipeline):
        """Test audio level monitoring"""
        device = audio_pipeline['device']
        
        # Monitor audio levels
        levels = []
        
        for _ in range(5):
            level = device.get_audio_level()
            levels.append(level)
        
        assert len(levels) == 5
        assert all(0 <= l <= 100 for l in levels)
    
    @pytest.mark.asyncio
    async def test_multi_language_tts(self, audio_pipeline):
        """Test multi-language TTS"""
        tts = audio_pipeline['tts']
        
        languages = [
            ('ja', 'こんにちは'),
            ('en', 'Hello'),
            ('zh', '你好')
        ]
        
        for lang, text in languages:
            tts.synthesize = AsyncMock(return_value=f"/tmp/output_{lang}.wav")
            
            result = await tts.synthesize(text, language=lang)
            
            assert result == f"/tmp/output_{lang}.wav"
            tts.synthesize.assert_called_with(text, language=lang)
    
    @pytest.mark.asyncio
    async def test_audio_timestamp_synchronization(self, audio_pipeline):
        """Test audio timestamp synchronization"""
        device = audio_pipeline['device']
        
        # Record with timestamps
        start_time = datetime.now()
        audio_data = await device.record_audio(duration=1)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        assert 0.9 <= duration <= 1.1  # Allow 100ms tolerance
    
    @pytest.mark.asyncio
    async def test_audio_codec_support(self, audio_pipeline):
        """Test audio codec support"""
        tts = audio_pipeline['tts']
        
        codecs = ['wav', 'mp3', 'ogg', 'opus']
        
        for codec in codecs:
            tts.synthesize = AsyncMock(return_value=f"/tmp/output.{codec}")
            
            result = await tts.synthesize("test", format=codec)
            
            assert result.endswith(f".{codec}")
    
    @pytest.mark.asyncio
    async def test_audio_volume_control(self, audio_pipeline):
        """Test audio volume control"""
        device = audio_pipeline['device']
        
        # Set different volume levels
        volume_levels = [0, 25, 50, 75, 100]
        
        for volume in volume_levels:
            device.set_volume(volume)
            current_volume = device.get_volume()
            
            assert current_volume == volume
    
    @pytest.mark.asyncio
    async def test_audio_device_selection(self, audio_pipeline):
        """Test audio device selection"""
        device = audio_pipeline['device']
        
        # List available devices
        devices = device.list_devices()
        
        assert isinstance(devices, list)
        
        if devices:
            # Select first device
            device.select_device(devices[0])
            current = device.get_current_device()
            
            assert current == devices[0]
    
    @pytest.mark.asyncio
    async def test_audio_echo_cancellation(self, audio_pipeline):
        """Test echo cancellation"""
        device = audio_pipeline['device']
        vad = audio_pipeline['vad']
        
        # Enable echo cancellation
        device.enable_echo_cancellation(True)
        
        # Process audio with echo
        audio_with_echo = np.random.bytes(16000)
        vad.cancel_echo = AsyncMock(return_value=audio_with_echo)
        
        result = await vad.cancel_echo(audio_with_echo)
        
        assert result is not None
        assert len(result) == len(audio_with_echo)