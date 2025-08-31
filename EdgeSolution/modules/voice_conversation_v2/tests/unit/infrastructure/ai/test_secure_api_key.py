"""
Secure API Key Management Test
Tests for Key Vault + Environment Variable fallback strategy
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
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

from infrastructure.ai.llm_client import LLMClient
from infrastructure.ai.stt_client import STTClient


class TestSecureAPIKeyManagement:
    """Test secure API key management with fallback strategy"""
    
    def setup_method(self):
        """Setup test environment"""
        # Clear environment variables
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
    
    def teardown_method(self):
        """Clean up test environment"""
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']
    
    @patch('infrastructure.ai.llm_client.KeyVaultClient')
    @patch('infrastructure.ai.llm_client.OpenAI')
    def test_llm_client_key_vault_priority(self, mock_openai, mock_key_vault_class):
        """Test LLMClient prioritizes Key Vault over environment variables"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_instance = Mock()
        mock_key_vault_class.return_value = mock_key_vault_instance
        mock_key_vault_instance.get_secret.return_value = "key-vault-api-key"
        
        # Set environment variable (should be ignored when Key Vault succeeds)
        os.environ['OPENAI_API_KEY'] = "env-api-key"
        
        # Act
        client = LLMClient(mock_config_loader)
        
        # Assert
        mock_key_vault_instance.get_secret.assert_called_once_with("openai-api-key")
        mock_openai.assert_called_once_with(api_key="key-vault-api-key", http_client=mock_openai.return_value)
    
    @patch('infrastructure.ai.llm_client.KeyVaultClient')
    @patch('infrastructure.ai.llm_client.OpenAI')
    def test_llm_client_environment_fallback(self, mock_openai, mock_key_vault_class):
        """Test LLMClient falls back to environment variable when Key Vault fails"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_instance = Mock()
        mock_key_vault_class.return_value = mock_key_vault_instance
        mock_key_vault_instance.get_secret.return_value = None  # Key Vault returns None
        
        os.environ['OPENAI_API_KEY'] = "env-fallback-key"
        
        # Act
        client = LLMClient(mock_config_loader)
        
        # Assert
        mock_key_vault_instance.get_secret.assert_called_once_with("openai-api-key")
        mock_openai.assert_called_once_with(api_key="env-fallback-key", http_client=mock_openai.return_value)
    
    @patch('infrastructure.ai.llm_client.KeyVaultClient')
    @patch('infrastructure.ai.llm_client.OpenAI')
    def test_llm_client_key_vault_exception_fallback(self, mock_openai, mock_key_vault_class):
        """Test LLMClient falls back when Key Vault access throws exception"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_class.side_effect = Exception("Key Vault connection failed")
        
        os.environ['OPENAI_API_KEY'] = "env-exception-fallback"
        
        # Act
        client = LLMClient(mock_config_loader)
        
        # Assert
        mock_openai.assert_called_once_with(api_key="env-exception-fallback", http_client=mock_openai.return_value)
    
    @patch('infrastructure.ai.llm_client.KeyVaultClient')
    @patch('infrastructure.ai.llm_client.OpenAI')
    def test_llm_client_no_api_key_found(self, mock_openai, mock_key_vault_class):
        """Test LLMClient handles case when no API key is found anywhere"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_instance = Mock()
        mock_key_vault_class.return_value = mock_key_vault_instance
        mock_key_vault_instance.get_secret.return_value = None
        # No environment variable set
        
        # Act
        client = LLMClient(mock_config_loader)
        
        # Assert
        assert client.client is None
        mock_openai.assert_not_called()
    
    @patch('infrastructure.ai.stt_client.KeyVaultClient')
    @patch('infrastructure.ai.stt_client.OpenAI')
    def test_stt_client_secure_key_management(self, mock_openai, mock_key_vault_class):
        """Test STTClient implements same secure key management strategy"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_instance = Mock()
        mock_key_vault_class.return_value = mock_key_vault_instance
        mock_key_vault_instance.get_secret.return_value = "stt-key-vault-key"
        
        # Act
        with patch('threading.Thread'):  # Prevent warmup thread from starting
            client = STTClient(mock_config_loader)
        
        # Assert
        mock_key_vault_instance.get_secret.assert_called_once_with("openai-api-key")
        mock_openai.assert_called_once_with(api_key="stt-key-vault-key", http_client=mock_openai.return_value)
    
    def test_secure_api_key_consistency(self):
        """Test that both clients use the same secure API key method"""
        mock_config_loader = Mock()
        
        # Both clients should have the same _get_secure_api_key method
        with patch('infrastructure.ai.llm_client.KeyVaultClient'), \
             patch('infrastructure.ai.llm_client.OpenAI'), \
             patch('infrastructure.ai.stt_client.KeyVaultClient'), \
             patch('infrastructure.ai.stt_client.OpenAI'), \
             patch('threading.Thread'):
            
            llm_client = LLMClient(mock_config_loader)
            stt_client = STTClient(mock_config_loader)
            
            # Both should have the secure API key method
            assert hasattr(llm_client, '_get_secure_api_key')
            assert hasattr(stt_client, '_get_secure_api_key')
    
    @patch('infrastructure.ai.llm_client.KeyVaultClient')
    def test_api_key_logging_security(self, mock_key_vault_class):
        """Test that API keys are never logged in plain text"""
        # Arrange
        mock_config_loader = Mock()
        mock_key_vault_instance = Mock()
        mock_key_vault_class.return_value = mock_key_vault_instance
        mock_key_vault_instance.get_secret.return_value = "secret-api-key-12345"
        
        # Act & Assert
        with patch('infrastructure.ai.llm_client.OpenAI') as mock_openai, \
             patch('logging.getLogger') as mock_get_logger:
            
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger
            
            client = LLMClient(mock_config_loader)
            
            # Verify that no log call contains the actual API key
            for call in mock_logger.info.call_args_list + mock_logger.warning.call_args_list:
                call_str = str(call)
                assert "secret-api-key-12345" not in call_str
                assert "secret" not in call_str.lower() or "retrieved" in call_str.lower()