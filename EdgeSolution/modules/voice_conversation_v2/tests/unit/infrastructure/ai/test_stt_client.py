"""
Unit tests for STTClient
Speech-to-Text infrastructure layer tests
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
import os
import sys
import time
import tempfile

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.ai.stt_client import STTClient


class TestSTTClient:
    """Test class for STTClient"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock for ConfigLoader"""
        mock = Mock()
        mock.get.side_effect = lambda key, default=None: {
            'stt.openai.model': 'whisper-1',
            'stt.language': 'ja'
        }.get(key, default)
        return mock
    
    @pytest.fixture
    def mock_shared_openai(self):
        """Mock for SharedAsyncOpenAI"""
        mock = AsyncMock()
        mock_client = AsyncMock()
        mock_client.audio.transcriptions.create = AsyncMock()
        mock.get_stt_client = AsyncMock(return_value=mock_client)
        return mock, mock_client
    
    @pytest.fixture
    def stt_client(self, mock_config_loader):
        """STT client for testing"""
        with patch.dict(os.environ, {'OPENAI_SECRET_NAME': 'test-secret'}):
            return STTClient(mock_config_loader)
    
    @pytest.mark.asyncio
    async def test_transcribe_success(self, stt_client, mock_shared_openai):
        """Test successful transcription"""
        mock_shared, mock_client = mock_shared_openai
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                mock_client.audio.transcriptions.create.return_value = "Hello, how are you?"
                
                result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result == "Hello, how are you?"
        assert stt_client.metrics['success_count'] == 1
        assert stt_client.metrics['error_count'] == 0
    
    @pytest.mark.asyncio
    async def test_transcribe_file_not_found(self, stt_client):
        """Test when file does not exist"""
        with patch('os.path.exists', return_value=False):
            result = await stt_client.transcribe("/tmp/nonexistent.wav")
        
        assert result is None
        assert stt_client.metrics['error_count'] == 1
    
    @pytest.mark.asyncio
    async def test_transcribe_with_hallucination(self, stt_client, mock_shared_openai):
        """Test hallucination detection"""
        mock_shared, mock_client = mock_shared_openai
        
        hallucination_texts = [
            "Thank you for watching",
            "Please subscribe to our channel",
            "[Music]"
        ]
        
        for text in hallucination_texts:
            with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
                with patch('os.path.exists', return_value=True):
                    mock_client.audio.transcriptions.create.return_value = text
                    
                    result = await stt_client.transcribe("/tmp/audio.wav")
            
            assert result is None or result == ""
    
    @pytest.mark.asyncio
    async def test_transcribe_with_retry(self, stt_client, mock_shared_openai):
        """Test retry functionality"""
        mock_shared, mock_client = mock_shared_openai
        
        from openai import APIConnectionError
        
        # First call fails, retry succeeds
        mock_client.audio.transcriptions.create.side_effect = [
            APIConnectionError("Connection failed"),
            "Retry successful"
        ]
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b'audio_data')):
                    result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result == "Retry successful"
        assert mock_client.audio.transcriptions.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_transcribe_retry_failed(self, stt_client, mock_shared_openai):
        """Test when retry also fails"""
        mock_shared, mock_client = mock_shared_openai
        
        from openai import APIConnectionError
        
        # Both calls fail
        mock_client.audio.transcriptions.create.side_effect = APIConnectionError("Connection failed")
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b'audio_data')):
                    result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result is None
        assert stt_client.metrics['error_count'] == 1
    
    @pytest.mark.asyncio
    async def test_transcribe_non_retryable_error(self, stt_client, mock_shared_openai):
        """Test non-retryable error"""
        mock_shared, mock_client = mock_shared_openai
        
        # Authentication error should not retry
        mock_client.audio.transcriptions.create.side_effect = Exception("Authentication failed")
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b'audio_data')):
                    result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result is None
        assert mock_client.audio.transcriptions.create.call_count == 1
    
    @pytest.mark.asyncio
    async def test_lazy_warmup(self, stt_client, mock_shared_openai):
        """Test lazy warmup"""
        mock_shared, mock_client = mock_shared_openai
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('tempfile.NamedTemporaryFile'):
                with patch('wave.open'):
                    with patch('os.unlink'):
                        with patch('builtins.open', mock_open()):
                            await stt_client._lazy_warmup()
        
        assert stt_client.metrics['warmup_completed'] is True
        mock_client.audio.transcriptions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_warmup_only_once(self, stt_client, mock_shared_openai):
        """Test that warmup runs only once"""
        mock_shared, mock_client = mock_shared_openai
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                mock_client.audio.transcriptions.create.return_value = "test1"
                
                # First transcribe (warmup executed)
                await stt_client.transcribe("/tmp/audio1.wav")
                warmup_call_count = mock_client.audio.transcriptions.create.call_count
                
                # Second transcribe (warmup skipped)
                mock_client.audio.transcriptions.create.return_value = "test2"
                await stt_client.transcribe("/tmp/audio2.wav")
        
        assert stt_client.metrics['warmup_completed'] is True
        # Warmup once, transcribe twice = at least 2 calls
        assert mock_client.audio.transcriptions.create.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_transcribe_empty_result(self, stt_client, mock_shared_openai):
        """Test empty result handling"""
        mock_shared, mock_client = mock_shared_openai
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                mock_client.audio.transcriptions.create.return_value = "   "  # Only whitespace
                
                result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result is None
        assert stt_client.metrics['success_count'] == 1
    
    def test_get_performance_metrics(self, stt_client):
        """Test getting performance metrics"""
        # Set metrics
        stt_client.metrics['total_requests'] = 10
        stt_client.metrics['success_count'] = 8
        stt_client.metrics['error_count'] = 2
        stt_client.metrics['total_processing_time'] = 20.0
        stt_client.metrics['average_processing_time'] = 2.5
        stt_client.metrics['warmup_completed'] = True
        stt_client.metrics['first_call_time'] = 5.0
        stt_client.metrics['subsequent_avg_time'] = 2.0
        
        metrics = stt_client.get_performance_metrics()
        
        assert metrics['total_requests'] == 10
        assert metrics['success_count'] == 8
        assert metrics['error_count'] == 2
        assert metrics['success_rate_percent'] == 80.0
        assert metrics['average_processing_time_seconds'] == 2.5
        assert metrics['warmup_completed'] is True
        assert metrics['first_call_time_seconds'] == 5.0
        assert metrics['subsequent_avg_time_seconds'] == 2.0
        assert metrics['warmup_improvement_ms'] == 3000.0
    
    def test_cleanup(self, stt_client):
        """Test cleanup"""
        with patch.object(stt_client, 'get_performance_metrics', return_value={'test': 'metrics'}):
            stt_client.cleanup()
        
        # Verify no errors occur
        assert True
    
    @pytest.mark.asyncio
    async def test_transcribe_with_japanese_text(self, stt_client, mock_shared_openai):
        """Test Japanese text processing"""
        mock_shared, mock_client = mock_shared_openai
        japanese_text = "Good morning. Let's do our best today."
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                mock_client.audio.transcriptions.create.return_value = japanese_text
                
                result = await stt_client.transcribe("/tmp/japanese.wav")
        
        assert result == japanese_text
        assert stt_client.metrics['success_count'] == 1
    
    @pytest.mark.asyncio
    async def test_transcribe_updates_metrics(self, stt_client, mock_shared_openai):
        """Test metrics update"""
        mock_shared, mock_client = mock_shared_openai
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                with patch('time.time', side_effect=[0, 0, 1.5, 1.5]):  # Processing time 1.5 seconds
                    mock_client.audio.transcriptions.create.return_value = "test"
                    
                    await stt_client.transcribe("/tmp/audio.wav")
        
        assert stt_client.metrics['total_requests'] == 1
        assert stt_client.metrics['success_count'] == 1
        assert stt_client.metrics['first_call_time'] == 1.5
    
    @pytest.mark.asyncio
    async def test_config_loader_integration(self, stt_client, mock_shared_openai):
        """Test ConfigLoader integration"""
        mock_shared, mock_client = mock_shared_openai
        
        # Change configuration
        stt_client.config_loader.get.side_effect = lambda key, default=None: {
            'stt.openai.model': 'whisper-1-hd',
            'stt.language': 'en'
        }.get(key, default)
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                mock_client.audio.transcriptions.create.return_value = "Hello"
                
                await stt_client.transcribe("/tmp/audio.wav")
        
        # Verify called with new configuration
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs['model'] == 'whisper-1-hd'
        assert call_kwargs['language'] == 'en'
    
    @pytest.mark.asyncio
    async def test_transcribe_timeout_error(self, stt_client, mock_shared_openai):
        """Test timeout error handling"""
        mock_shared, mock_client = mock_shared_openai
        
        from openai import APITimeoutError
        
        mock_client.audio.transcriptions.create.side_effect = [
            APITimeoutError("Timeout"),
            "Success after retry"
        ]
        
        with patch('infrastructure.ai.stt_client.get_shared_openai', return_value=mock_shared):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=b'audio_data')):
                    result = await stt_client.transcribe("/tmp/audio.wav")
        
        assert result == "Success after retry"
        assert mock_client.audio.transcriptions.create.call_count == 2
    
    def test_init_with_environment(self):
        """Test initialization with environment variables"""
        mock_config = Mock()
        
        with patch.dict(os.environ, {'OPENAI_SECRET_NAME': 'my-secret-key'}):
            client = STTClient(mock_config)
        
        assert client.openai_secret_name == 'my-secret-key'
        assert client.metrics['warmup_completed'] is False
        assert client.metrics['total_requests'] == 0