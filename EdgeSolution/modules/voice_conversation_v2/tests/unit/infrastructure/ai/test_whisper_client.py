"""
Unit tests for WhisperClient
Tests speech recognition processing implementation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock whisper module
sys.modules['whisper'] = MagicMock()

from infrastructure.ai.stt_client import STTClient


class TestWhisperClient:
    """Test class for WhisperClient"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock for configuration"""
        return {
            "model_name": "base",
            "language": "ja"
        }
    
    @pytest.fixture
    @patch('infrastructure.ai.whisper_client.whisper')
    def client(self, mock_whisper, mock_config):
        """Client under test"""
        mock_model = Mock()
        mock_whisper.load_model.return_value = mock_model
        return WhisperClient(mock_config)
    
    @patch('infrastructure.ai.whisper_client.whisper')
    def test_init(self, mock_whisper, mock_config):
        """Test initialization"""
        # Setup
        mock_model = Mock()
        mock_whisper.load_model.return_value = mock_model
        
        # Execute
        client = WhisperClient(mock_config)
        
        # Verify
        assert client.model_name == "base"
        assert client.language == "ja"
        mock_whisper.load_model.assert_called_once_with("base")
    
    @patch('os.path.exists')
    def test_transcribe_success(self, mock_exists, client):
        """Test successful speech recognition"""
        # Setup
        mock_exists.return_value = True
        client.model.transcribe.return_value = {
            'text': '  Hello  '
        }
        
        # Execute
        result = client.transcribe("/tmp/audio.wav")
        
        # Verify
        assert result == "Hello"  # Leading/trailing whitespace removed
        client.model.transcribe.assert_called_once_with(
            "/tmp/audio.wav",
            language="ja",
            fp16=False
        )
    
    @patch('os.path.exists')
    def test_transcribe_file_not_found(self, mock_exists, client):
        """Test when file does not exist"""
        # Setup
        mock_exists.return_value = False
        
        # Execute
        result = client.transcribe("/tmp/nonexistent.wav")
        
        # Verify
        assert result is None
        client.model.transcribe.assert_not_called()
    
    @patch('os.path.exists')
    def test_transcribe_hallucination(self, mock_exists, client):
        """Test hallucination detection"""
        # Setup
        mock_exists.return_value = True
        client.model.transcribe.return_value = {
            'text': 'Thank you for watching'
        }
        
        # Execute
        result = client.transcribe("/tmp/audio.wav")
        
        # Verify
        assert result == ""  # Hallucination returns empty string
    
    @patch('os.path.exists')
    def test_transcribe_error(self, mock_exists, client):
        """Test speech recognition error"""
        # Setup
        mock_exists.return_value = True
        client.model.transcribe.side_effect = Exception("Transcribe error")
        
        # Execute
        result = client.transcribe("/tmp/audio.wav")
        
        # Verify
        assert result is None
    
    def test_is_hallucination(self, client):
        """Test hallucination determination"""
        # Hallucination cases
        hallucination_texts = [
            "Thank you for watching",
            "Please subscribe to our channel",
            "Please give us a thumbs up",
            "Leave your comments below",
            "See you in the next video",
            "Ending the stream",
            "Currently live streaming"
        ]
        
        for text in hallucination_texts:
            assert client._is_hallucination(text) is True
        
        # Normal texts
        normal_texts = [
            "Hello",
            "It's nice weather today",
            "How are you?"
        ]
        
        for text in normal_texts:
            assert client._is_hallucination(text) is False
    
    def test_update_config(self, client):
        """Test configuration update (no model change)"""
        # Setup
        new_config = {
            "model_name": "base",  # Same model
            "language": "en"
        }
        
        # Execute
        client.update_config(new_config)
        
        # Verify
        assert client.language == "en"
    
    @patch('infrastructure.ai.whisper_client.whisper')
    def test_update_config_model_change(self, mock_whisper, client):
        """Test configuration update (with model change)"""
        # Setup
        new_model = Mock()
        mock_whisper.load_model.return_value = new_model
        new_config = {
            "model_name": "small",
            "language": "ja"
        }
        
        # Execute
        client.update_config(new_config)
        
        # Verify
        assert client.model_name == "small"
        mock_whisper.load_model.assert_called_with("small")
        assert client.model == new_model