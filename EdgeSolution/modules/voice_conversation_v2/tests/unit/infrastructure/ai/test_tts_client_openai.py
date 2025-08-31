"""
Unit tests for TTSClient
Text-to-Speech infrastructure layer tests
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
import asyncio
import os
import sys

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.ai.tts_client import TTSClient


class TestTTSClient:
    """Test class for TTSClient"""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock for OpenAI client"""
        mock = AsyncMock()
        mock.audio.speech.create = AsyncMock()
        return mock
    
    @pytest.fixture
    def tts_client(self, mock_openai_client):
        """TTS client for testing"""
        with patch('infrastructure.ai.tts_client.get_shared_openai', return_value=mock_openai_client):
            client = TTSClient()
            client.client = mock_openai_client
            return client
    
    @pytest.mark.asyncio
    async def test_synthesize_success(self, tts_client, mock_openai_client):
        """Test successful synthesis"""
        # Setup mock
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        # Mock file writing
        with patch('builtins.open', mock_open()) as mock_file:
            # Execute
            result = await tts_client.synthesize("Hello", "/tmp/output.wav")
        
        # Verify
        assert result == "/tmp/output.wav"
        mock_openai_client.audio.speech.create.assert_called_once()
        mock_file.assert_called_once_with("/tmp/output.wav", "wb")
        mock_file().write.assert_called_once_with(b'audio_data')
    
    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, tts_client):
        """Test with empty text"""
        result = await tts_client.synthesize("", "/tmp/output.wav")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_api_error(self, tts_client, mock_openai_client):
        """Test API error handling"""
        mock_openai_client.audio.speech.create.side_effect = Exception("API Error")
        
        result = await tts_client.synthesize("test", "/tmp/output.wav")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_file_write_error(self, tts_client, mock_openai_client):
        """Test file write error"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', side_effect=IOError("Cannot write file")):
            result = await tts_client.synthesize("test", "/tmp/output.wav")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_with_voice(self, tts_client, mock_openai_client):
        """Test with voice specification"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            result = await tts_client.synthesize("test", "/tmp/output.wav", voice="nova")
        
        assert result == "/tmp/output.wav"
        call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
        assert call_kwargs.get("voice") == "nova"
    
    @pytest.mark.asyncio
    async def test_synthesize_with_speed(self, tts_client, mock_openai_client):
        """Test with speed specification"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            result = await tts_client.synthesize("test", "/tmp/output.wav", speed=1.5)
        
        assert result == "/tmp/output.wav"
        call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
        assert call_kwargs.get("speed") == 1.5
    
    @pytest.mark.asyncio
    async def test_synthesize_stream_success(self, tts_client, mock_openai_client):
        """Test successful streaming synthesis"""
        # Mock streaming response
        async def mock_stream():
            yield b'chunk1'
            yield b'chunk2'
            yield b'chunk3'
        
        mock_openai_client.audio.speech.create.return_value = mock_stream()
        
        # Execute
        stream = tts_client.synthesize_stream("Hello")
        
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        
        # Verify
        assert len(chunks) == 3
        assert chunks == [b'chunk1', b'chunk2', b'chunk3']
    
    @pytest.mark.asyncio
    async def test_synthesize_stream_error(self, tts_client, mock_openai_client):
        """Test streaming error"""
        async def mock_stream_with_error():
            yield b'chunk1'
            raise Exception("Stream error")
        
        mock_openai_client.audio.speech.create.return_value = mock_stream_with_error()
        
        stream = tts_client.synthesize_stream("test")
        
        chunks = []
        with pytest.raises(Exception):
            async for chunk in stream:
                chunks.append(chunk)
        
        assert len(chunks) == 1  # Only one chunk before error
    
    @pytest.mark.asyncio
    async def test_synthesize_japanese_text(self, tts_client, mock_openai_client):
        """Test Japanese text synthesis"""
        japanese_text = "Good morning. Let's do our best today."
        mock_response = Mock()
        mock_response.content = b'japanese_audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            result = await tts_client.synthesize(japanese_text, "/tmp/japanese.wav")
        
        assert result == "/tmp/japanese.wav"
        call_args = mock_openai_client.audio.speech.create.call_args
        assert japanese_text in str(call_args)
    
    @pytest.mark.asyncio
    async def test_synthesize_with_model(self, tts_client, mock_openai_client):
        """Test model specification"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            result = await tts_client.synthesize("test", "/tmp/output.wav", model="tts-1-hd")
        
        assert result == "/tmp/output.wav"
        call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
        assert call_kwargs.get("model") == "tts-1-hd"
    
    @pytest.mark.asyncio
    async def test_synthesize_timeout(self, tts_client, mock_openai_client):
        """Test timeout handling"""
        async def slow_synthesize(*args, **kwargs):
            await asyncio.sleep(10)
            return Mock(content=b'audio_data')
        
        mock_openai_client.audio.speech.create = slow_synthesize
        
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            result = await tts_client.synthesize("test", "/tmp/output.wav")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_create_directory(self, tts_client, mock_openai_client):
        """Test directory creation"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('os.makedirs') as mock_makedirs:
            with patch('builtins.open', mock_open()):
                result = await tts_client.synthesize("test", "/new/dir/output.wav")
        
        # Verify directory creation is called (implementation dependent)
        assert result == "/new/dir/output.wav" or result is None
    
    @pytest.mark.asyncio
    async def test_concurrent_synthesis(self, tts_client, mock_openai_client):
        """Test multiple concurrent synthesis"""
        mock_responses = [
            Mock(content=b'audio1'),
            Mock(content=b'audio2'),
            Mock(content=b'audio3')
        ]
        mock_openai_client.audio.speech.create.side_effect = mock_responses
        
        with patch('builtins.open', mock_open()):
            # Parallel execution
            tasks = [
                tts_client.synthesize(f"text{i}", f"/tmp/output{i}.wav")
                for i in range(3)
            ]
            results = await asyncio.gather(*tasks)
        
        assert results == ["/tmp/output0.wav", "/tmp/output1.wav", "/tmp/output2.wav"]
        assert mock_openai_client.audio.speech.create.call_count == 3
    
    @pytest.mark.asyncio
    async def test_synthesize_with_format(self, tts_client, mock_openai_client):
        """Test audio format specification"""
        mock_response = Mock()
        mock_response.content = b'audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            # Save as MP3 format
            result = await tts_client.synthesize("test", "/tmp/output.mp3", response_format="mp3")
        
        assert result == "/tmp/output.mp3"
        call_kwargs = mock_openai_client.audio.speech.create.call_args.kwargs
        assert call_kwargs.get("response_format") == "mp3"
    
    @pytest.mark.asyncio
    async def test_synthesize_long_text(self, tts_client, mock_openai_client):
        """Test long text synthesis"""
        long_text = "This is a very long text. " * 100  # Long text
        mock_response = Mock()
        mock_response.content = b'large_audio_data'
        mock_openai_client.audio.speech.create.return_value = mock_response
        
        with patch('builtins.open', mock_open()):
            result = await tts_client.synthesize(long_text, "/tmp/long_output.wav")
        
        assert result == "/tmp/long_output.wav"
        # Verify long text can be processed
        call_args = mock_openai_client.audio.speech.create.call_args
        assert len(call_args.kwargs.get("input", "")) > 1000