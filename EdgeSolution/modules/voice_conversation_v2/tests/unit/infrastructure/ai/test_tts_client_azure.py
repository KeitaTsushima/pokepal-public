"""
Unit tests for TTSClient
Tests Azure Speech text-to-speech processing implementation
"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['azure.cognitiveservices'] = MagicMock()
sys.modules['azure.cognitiveservices.speech'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.ai.tts_client import TTSClient


class TestTTSClient:
    """Test class for TTSClient"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        return {
            "region": "japaneast",
            "voice_name": "ja-JP-NanamiNeural",
            "speech_rate": 1.0,
            "speech_pitch": 0
        }
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment variables"""
        with patch.dict(os.environ, {"AZURE_SPEECH_KEY": "test-key"}):
            yield
    
    @pytest.fixture
    def mock_speechsdk(self):
        """Mock Azure Speech SDK"""
        with patch('infrastructure.ai.tts_client.speechsdk') as mock_sdk:
            # SpeechConfig mock
            mock_speech_config = Mock()
            mock_sdk.SpeechConfig.return_value = mock_speech_config
            
            # AudioOutputConfig mock
            mock_audio_config = Mock()
            mock_sdk.audio.AudioOutputConfig.return_value = mock_audio_config
            
            # SpeechSynthesizer mock
            mock_synthesizer = Mock()
            mock_sdk.SpeechSynthesizer.return_value = mock_synthesizer
            
            # Enum values as constants (not MagicMock)
            mock_sdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3 = "mock_format"
            mock_sdk.ResultReason.SynthesizingAudioCompleted = "SynthesizingAudioCompleted"
            mock_sdk.ResultReason.Canceled = "Canceled"
            
            # Result mock with correct enum value
            mock_result = Mock()
            mock_result.reason = "SynthesizingAudioCompleted"  # Use the actual string value
            mock_synthesizer.speak_ssml_async.return_value.get.return_value = mock_result
            
            yield mock_sdk
    
    @pytest.fixture
    def client(self, mock_config, mock_env, mock_speechsdk):
        """Client under test"""
        return TTSClient(mock_config)
    
    def test_init_success(self, mock_config, mock_env, mock_speechsdk):
        """Test successful initialization"""
        client = TTSClient(mock_config)
        
        assert client.region == "japaneast"
        assert client.core_synthesizer.voice_name == "ja-JP-NanamiNeural"
        assert client.core_synthesizer.speech_rate == 1.0
        assert client.core_synthesizer.speech_pitch == 0
        
        # Verify SpeechConfig was called
        mock_speechsdk.SpeechConfig.assert_called_once_with(
            subscription="test-key",
            region="japaneast"
        )
    
    def test_init_missing_api_key(self, mock_config, mock_speechsdk):
        """Test with missing API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AZURE_SPEECH_KEY environment variable required"):
                TTSClient(mock_config)
    
    def test_init_missing_speechsdk(self, mock_config, mock_env):
        """Test with Azure Speech SDK not installed"""
        with patch('infrastructure.ai.tts_client.speechsdk', None):
            with pytest.raises(ImportError, match="Azure Speech SDK not available"):
                TTSClient(mock_config)
    
    def test_synthesize_success(self, client, mock_speechsdk):
        """Test successful speech synthesis"""
        # Execute
        result = client.synthesize("Hello")
        
        # Verify
        assert result == "response.wav"
        
        # Verify SSML generation and synthesizer call
        mock_synthesizer = mock_speechsdk.SpeechSynthesizer.return_value
        mock_synthesizer.speak_ssml_async.assert_called_once()
        
        # Verify SSML content
        call_args = mock_synthesizer.speak_ssml_async.call_args[0][0]
        assert "Hello" in call_args
        assert "ja-JP-NanamiNeural" in call_args
        assert "rate=\"+0%\"" in call_args  # speech_rate 1.0 = +0%
        assert "pitch=\"+0%\"" in call_args  # speech_pitch 0 = +0%
    
    def test_synthesize_custom_output(self, client, mock_speechsdk):
        """Test speech synthesis with custom output file"""
        # Execute
        result = client.synthesize("Hello", "/tmp/custom.wav")
        
        # Verify
        assert result == "/tmp/custom.wav"
        
        # Verify AudioOutputConfig called with correct filename
        mock_speechsdk.audio.AudioOutputConfig.assert_called_with(filename="/tmp/custom.wav")
    
    def test_synthesize_canceled(self, client, mock_speechsdk):
        """Test speech synthesis cancellation"""
        # Setup: Mock cancellation result
        mock_result = Mock()
        mock_result.reason = "Canceled"  # Use string value
        mock_result.cancellation_details.reason = "TestCancellation"
        mock_result.cancellation_details.error_details = "Test error"
        
        mock_synthesizer = mock_speechsdk.SpeechSynthesizer.return_value
        mock_synthesizer.speak_ssml_async.return_value.get.return_value = mock_result
        
        # Execute
        result = client.synthesize("Hello")
        
        # Verify
        assert result is None
    
    def test_synthesize_exception(self, client, mock_speechsdk):
        """Test exception handling"""
        # Setup: Raise exception
        mock_synthesizer = mock_speechsdk.SpeechSynthesizer.return_value
        mock_synthesizer.speak_ssml_async.side_effect = Exception("Test exception")
        
        # Execute
        result = client.synthesize("Hello")
        
        # Verify
        assert result is None
    
    def test_update_config(self, client):
        """Test configuration update"""
        # Setup: Set new values in ConfigLoader
        client.config_loader.update({
            "tts": {
                "voice_name": "ja-JP-KeitaNeural",
                "speech_rate": 1.2,
                "speech_pitch": 10
            }
        })
        
        # Execute
        client.update_config()
        
        # Verify
        assert client.core_synthesizer.voice_name == "ja-JP-KeitaNeural"
        assert client.core_synthesizer.speech_rate == 1.2
        assert client.core_synthesizer.speech_pitch == 10
    
    def test_should_use_streaming_true(self, client):
        """Test streaming determination: true"""
        # Long text (80+ characters)
        long_text = "This is a very long text. " * 5  # 80+ characters
        assert client.should_use_streaming(long_text) is True
        
        # 3 or more sentences
        multi_sentence = "Hello. It's nice weather today. How are you?"
        assert client.should_use_streaming(multi_sentence) is True
    
    def test_should_use_streaming_false(self, client):
        """Test streaming determination: false"""
        # Short text
        short_text = "Hello."
        assert client.should_use_streaming(short_text) is False
        
        # 2 or less sentences and less than 80 characters
        two_sentences = "Hello. It's nice weather today."
        assert client.should_use_streaming(two_sentences) is False
    
    def test_split_sentences(self, client):
        """Test sentence splitting"""
        text = "Hello. It's nice weather today! How are you?"
        sentences = client._split_sentences(text)
        
        expected = ["Hello.", "It's nice weather today!", "How are you?"]
        assert sentences == expected
    
    def test_calculate_dynamic_rate(self, client):
        """Test dynamic speech rate calculation"""
        # For single sentence, rate is 1.0
        assert client._calculate_dynamic_rate(0, 1) == 1.0
        
        # For multiple sentences
        assert client._calculate_dynamic_rate(0, 3) == 0.7  # Start
        assert client._calculate_dynamic_rate(1, 3) == 0.85  # Middle
        assert client._calculate_dynamic_rate(2, 3) == 1.0  # End
    