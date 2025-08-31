"""
Unit tests for OpenAIClient
Tests LLM response generation implementation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
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

from infrastructure.ai.llm_client import LLMClient


class TestLLMClient:
    """Test class for LLMClient"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock for ConfigLoader"""
        from unittest.mock import Mock
        mock_loader = Mock()
        mock_loader.get.side_effect = lambda key: {
            'llm.model': 'gpt-4o-mini',
            'llm.max_tokens': 500,
            'llm.temperature': 0.7
        }.get(key)
        return mock_loader
    
    @pytest.fixture
    def mock_messages(self):
        """Mock for message list"""
        from datetime import datetime
        now = datetime.now()
        return [
            Message(content="Hello", role=MessageRole.USER, timestamp=now),
            Message(content="Hello! It's nice weather today.", role=MessageRole.ASSISTANT, timestamp=now),
            Message(content="That's right", role=MessageRole.USER, timestamp=now)
        ]
    
    @pytest.fixture
    @patch('os.getenv')
    def client(self, mock_getenv, mock_config_loader):
        """Client under test"""
        mock_getenv.return_value = "test-api-key"
        
        with patch('infrastructure.ai.llm_client.OpenAI') as mock_openai_class:
            mock_openai = Mock()
            mock_openai_class.return_value = mock_openai
            return LLMClient(mock_config_loader)
    
    @patch('os.getenv')
    def test_init_with_api_key(self, mock_getenv, mock_config_loader):
        """Test initialization with API key"""
        # Setup
        mock_getenv.return_value = "test-api-key"
        
        with patch('infrastructure.ai.llm_client.OpenAI') as mock_openai_class:
            # Execute
            client = LLMClient(mock_config_loader)
            
            # Verify
            assert client.config_loader == mock_config_loader
            mock_openai_class.assert_called_once()
    
    @patch('os.getenv')
    def test_init_without_api_key(self, mock_getenv, mock_config_loader):
        """Test initialization without API key"""
        # Setup
        mock_getenv.return_value = None
        
        # Execute
        client = LLMClient(mock_config_loader)
        
        # Verify
        assert client.client is None
    
    def test_generate_response_success(self, client, mock_messages):
        """Test successful response generation"""
        # Setup
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="I'm glad to hear you're doing well."))]
        client.client.chat.completions.create.return_value = mock_response
        
        # Execute
        system_prompt = "You are a kind companion for elderly people. Today's memory: We talked about morning walk."
        result = client.complete_chat(mock_messages, system_prompt)
        
        # Verify
        assert result == "I'm glad to hear you're doing well."
        
        # Verify API call (dynamically retrieved from ConfigLoader)
        call_args = client.client.chat.completions.create.call_args
        assert call_args.kwargs['model'] == "gpt-4o-mini"
        assert call_args.kwargs['max_tokens'] == 500
        assert call_args.kwargs['temperature'] == 0.7
        
        # Verify ConfigLoader was called
        client.config_loader.get.assert_any_call('llm.model')
        client.config_loader.get.assert_any_call('llm.max_tokens')
        client.config_loader.get.assert_any_call('llm.temperature')
        
        # Verify messages
        messages = call_args.kwargs['messages']
        assert messages[0]['role'] == 'system'
        assert "You are a kind companion for elderly people" in messages[0]['content']
        assert "Today's memory" in messages[0]['content']
        assert len(messages) == 4  # system + 3 messages
    
    def test_generate_response_no_client(self, client):
        """Test response generation without client"""
        # Setup
        client.client = None
        
        # Execute
        result = client.complete_chat([], "System prompt test")
        
        # Verify
        assert result is None
    
    def test_generate_response_error(self, client, mock_messages):
        """Test response generation error"""
        # Setup
        client.client.chat.completions.create.side_effect = Exception("API Error")
        
        # Execute
        system_prompt = "You are a kind companion for elderly people. Today's memory: We talked about morning walk."
        result = client.complete_chat(mock_messages, system_prompt)
        
        # Verify
        assert result is None
    
    def test_build_messages(self, client, mock_messages):
        """Test message construction"""
        # Execute
        system_prompt = "You are a kind companion for elderly people. Today's memory: We talked about morning walk."
        result = client._convert_to_api_format(mock_messages, system_prompt)
        
        # Verify
        assert len(result) == 4
        assert result[0]['role'] == 'system'
        assert "We talked about morning walk" in result[0]['content']
        assert result[1] == {'role': 'user', 'content': 'Hello'}
        assert result[2] == {'role': 'assistant', 'content': "Hello! It's nice weather today."}
        assert result[3] == {'role': 'user', 'content': "That's right"}
    
    def test_reinitialize_client(self, client):
        """Test client reinitialization"""
        # Setup: Set API key via environment variable
        with patch('os.getenv') as mock_getenv:
            mock_getenv.return_value = "new-api-key"
            
            # Execute
            client._reinitialize_client()
            
            # Verify: New client was created
            assert client.client is not None