"""
Unit tests for LLMClient
Tests LLM processing infrastructure layer
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import sys
import os

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.ai.llm_client import LLMClient


class TestLLMClient:
    """Test class for LLMClient"""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock for OpenAI client"""
        mock = Mock()
        mock.chat.completions.create = AsyncMock()
        return mock
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock for ConfigLoader"""
        mock = Mock()
        mock.get.side_effect = lambda key, default=None: {
            'llm.model': 'gpt-4',
            'llm.max_tokens': 500,
            'llm.temperature': 0.7
        }.get(key, default)
        return mock
    
    @pytest.fixture
    def llm_client(self, mock_openai_client, mock_config_loader):
        """LLMClient for testing"""
        with patch.dict('os.environ', {'OPENAI_SECRET_NAME': 'test-secret'}):
            client = LLMClient(mock_config_loader)
            return client
    
    @pytest.mark.asyncio
    async def test_complete_chat_success(self, llm_client, mock_openai_client):
        """Test successful complete_chat"""
        # Setup mock
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Hello! How are you?"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Mock SharedAsyncOpenAI
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "Hello"}]
        system_prompt = "You are a helpful assistant"
        
        # Execute
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            result = await llm_client.complete_chat(messages, system_prompt)
        
        # Verify
        assert result == "Hello! How are you?"
        mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_chat_with_empty_response(self, llm_client, mock_openai_client):
        """Test empty response handling"""
        mock_response = Mock()
        mock_response.choices = []
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            result = await llm_client.complete_chat(messages, "prompt")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_complete_chat_with_exception(self, llm_client, mock_openai_client):
        """Test exception handling"""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            result = await llm_client.complete_chat(messages, "prompt")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion_success(self, llm_client, mock_openai_client):
        """Test successful streaming"""
        # Mock streaming response
        async def mock_stream():
            yield Mock(choices=[Mock(delta=Mock(content="Hel"))])
            yield Mock(choices=[Mock(delta=Mock(content="lo"))])
            yield Mock(choices=[Mock(delta=Mock(content="!"))])
        
        mock_openai_client.chat.completions.create.return_value = mock_stream()
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        # Execute
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            stream = llm_client.stream_chat_completion(messages, "prompt")
            
            chunks = []
            async for chunk in stream:
                if chunk.get("type") == "delta":
                    chunks.append(chunk["text"])
        
        # Verify
        assert len(chunks) >= 3
        assert "".join(chunks[:3]) == "Hello!"
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion_with_error(self, llm_client, mock_openai_client):
        """Test streaming error handling"""
        async def mock_stream_with_error():
            yield Mock(choices=[Mock(delta=Mock(content="test"))])
            raise Exception("Stream error")
        
        mock_openai_client.chat.completions.create.return_value = mock_stream_with_error()
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            stream = llm_client.stream_chat_completion(messages, "prompt")
        
            events = []
            async for event in stream:
                events.append(event)
                if event.get("type") == "error":
                    break
        
        # Final event is always sent
        assert events[-1]["type"] == "final"
    
    @pytest.mark.asyncio
    async def test_stream_chat_completion_timeout(self, llm_client, mock_openai_client):
        """Test streaming timeout"""
        async def slow_stream():
            await asyncio.sleep(10)
            yield Mock(choices=[Mock(delta=Mock(content="test"))])
        
        mock_openai_client.chat.completions.create.return_value = slow_stream()
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            stream = llm_client.stream_chat_completion(messages, "prompt")
        
            with pytest.raises(asyncio.TimeoutError):
                async with asyncio.timeout(0.1):
                    async for _ in stream:
                        pass
    
    def test_convert_to_api_format_with_system_prompt(self, llm_client):
        """Test message conversion with system prompt"""
        messages = [{"role": "user", "content": "Hello"}]
        system_prompt = "You are helpful"
        
        result = llm_client._convert_to_api_format(messages, system_prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == system_prompt
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "Hello"
    
    def test_convert_to_api_format_without_system_prompt(self, llm_client):
        """Test message conversion without system prompt"""
        messages = [{"role": "user", "content": "Hello"}]
        
        # When system prompt is empty, default system message is added
        result = llm_client._convert_to_api_format(messages, "")
        
        # Default system message is added, so 2 messages
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_complete_chat_with_temperature(self, llm_client, mock_openai_client):
        """Test with temperature parameter"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="response"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        # Temperature is retrieved from config
        llm_client.config_loader.get.side_effect = lambda key, default=None: {
            'llm.model': 'gpt-4',
            'llm.max_tokens': 500,
            'llm.temperature': 0.5
        }.get(key, default)
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            await llm_client.complete_chat(messages, "prompt")
        
        # Verify create call arguments
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.5
    
    @pytest.mark.asyncio
    async def test_complete_chat_with_max_tokens(self, llm_client, mock_openai_client):
        """Test with max_tokens specification"""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="response"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        # max_tokens is retrieved from config
        llm_client.config_loader.get.side_effect = lambda key, default=None: {
            'llm.model': 'gpt-4',
            'llm.max_tokens': 100,
            'llm.temperature': 0.7
        }.get(key, default)
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            await llm_client.complete_chat(messages, "prompt")
        
        call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 100
    
    @pytest.mark.asyncio
    async def test_stream_final_event(self, llm_client, mock_openai_client):
        """Test streaming final event"""
        async def mock_stream():
            yield Mock(choices=[Mock(delta=Mock(content="Hello"))])
            yield Mock(choices=[Mock(delta=Mock(content=" World"))])
        
        mock_openai_client.chat.completions.create.return_value = mock_stream()
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        messages = [{"role": "user", "content": "test"}]
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            stream = llm_client.stream_chat_completion(messages, "prompt")
        
            events = []
            async for event in stream:
                events.append(event)
            
            # Verify final event
            assert events[-1]["type"] == "final"
            assert events[-1]["text"] == "Hello World"
    
    @pytest.mark.asyncio
    async def test_multiple_complete_chat_calls(self, llm_client, mock_openai_client):
        """Test multiple complete_chat calls"""
        responses = ["First", "Second", "Third"]
        mock_responses = []
        for text in responses:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=text))]
            mock_responses.append(mock_response)
        
        mock_openai_client.chat.completions.create.side_effect = mock_responses
        
        messages = [{"role": "user", "content": "test"}]
        
        mock_shared = AsyncMock()
        mock_shared.get_llm_client = AsyncMock(return_value=mock_openai_client)
        
        with patch('infrastructure.ai.llm_client.get_shared_openai', return_value=mock_shared):
            results = []
            for _ in range(3):
                result = await llm_client.complete_chat(messages, "prompt")
                results.append(result)
        
        assert results == responses
        assert mock_openai_client.chat.completions.create.call_count == 3