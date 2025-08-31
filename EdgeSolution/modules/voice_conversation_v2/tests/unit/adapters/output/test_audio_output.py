"""
Unit tests for AudioOutputAdapter
Tests audio output conversion processing
"""
import pytest
from unittest.mock import Mock, patch
from adapters.output.audio_output import AudioOutputAdapter


class TestAudioOutputAdapter:
    """Test class for AudioOutputAdapter"""
    
    @pytest.fixture
    def mock_tts_client(self):
        """Mock for TTSClient"""
        client = Mock()
        client.synthesize = Mock(return_value="/tmp/speech.wav")
        return client
    
    @pytest.fixture
    def mock_audio_device(self):
        """Mock for AudioDevice"""
        device = Mock()
        device.play = Mock(return_value=True)
        return device
    
    @pytest.fixture
    def adapter(self, mock_tts_client, mock_audio_device):
        """Adapter under test"""
        return AudioOutputAdapter(
            tts_client=mock_tts_client,
            audio_device=mock_audio_device
        )
    
    def test_init(self, adapter, mock_tts_client, mock_audio_device):
        """Test initialization"""
        assert adapter.tts_client == mock_tts_client
        assert adapter.audio_device == mock_audio_device
    
    def test_speak_success(self, adapter, mock_tts_client, mock_audio_device):
        """Test successful audio output"""
        # Execute
        adapter.speak("こんにちは")
        
        # Verify
        mock_tts_client.synthesize.assert_called_once_with("こんにちは")
        mock_audio_device.play.assert_called_once_with("/tmp/speech.wav")
    
    def test_speak_tts_error(self, adapter, mock_tts_client, mock_audio_device):
        """Test TTS synthesis error"""
        # Setup
        mock_tts_client.synthesize.side_effect = Exception("TTS error")
        
        # Execute
        adapter.speak("こんにちは")
        
        # Verify
        mock_tts_client.synthesize.assert_called_once()
        mock_audio_device.play.assert_not_called()
    
    def test_speak_playback_error(self, adapter, mock_tts_client, mock_audio_device):
        """Test playback error"""
        # Setup
        mock_audio_device.play.return_value = False
        
        # Execute
        adapter.speak("こんにちは")
        
        # Verify
        mock_tts_client.synthesize.assert_called_once()
        mock_audio_device.play.assert_called_once()
    
    def test_play_greeting(self, adapter):
        """Test greeting playback"""
        # Mock speak method as spy
        adapter.speak = Mock()
        
        # Execute
        adapter.play_greeting()
        
        # Verify
        adapter.speak.assert_called_once()
        # Verify greeting message is included
        call_args = adapter.speak.call_args[0][0]
        assert "こんにちは" in call_args or "音声対話" in call_args
    
    def test_play_audio_file(self, adapter, mock_audio_device):
        """Test audio file playback"""
        # Execute
        result = adapter.play_audio_file("/tmp/test.wav")
        
        # Verify
        assert result is True
        mock_audio_device.play.assert_called_once_with("/tmp/test.wav")