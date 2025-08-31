"""
Configuration management integration tests
Configuration management integration testing
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import json
import os
from datetime import datetime

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.iot'] = MagicMock()
sys.modules['azure.iot.device'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.config.config_loader import ConfigLoader
from infrastructure.config.twin_sync import TwinSync
from application.conversation_service import ConversationService
from application.proactive_service import ProactiveService
from infrastructure.iot.connection_manager import IoTConnectionManager


class TestConfigManagement:
    """Integration tests for configuration management"""
    
    @pytest.fixture
    def config_system(self):
        """Setup configuration management system"""
        config_loader = ConfigLoader()
        twin_sync = TwinSync(config_loader)
        
        # Mock IoT connection
        iot_manager = Mock(spec=IoTConnectionManager)
        iot_manager.register_twin_callback = Mock()
        iot_manager.send_reported_properties = AsyncMock()
        
        return {
            'config_loader': config_loader,
            'twin_sync': twin_sync,
            'iot_manager': iot_manager
        }
    
    @pytest.mark.asyncio
    async def test_config_file_loading_and_validation(self, config_system):
        """Test config file loading and validation integration"""
        config_loader = config_system['config_loader']
        
        # Mock config file
        config_data = {
            "llm": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500
            },
            "stt": {
                "language": "ja",
                "openai": {
                    "model": "whisper-1"
                }
            },
            "conversation": {
                "farewell_message": "Let's talk again",
                "fallback_message": "Sorry, please say that again"
            }
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(config_data)
            config_loader.load_from_file("/config/config.json")
        
        # Verify all config loaded
        assert config_loader.get('llm.model') == 'gpt-4'
        assert config_loader.get('stt.language') == 'ja'
        assert config_loader.get('conversation.farewell_message') == 'Let\'s talk again'
    
    @pytest.mark.asyncio
    async def test_twin_sync_with_config_update(self, config_system):
        """Test configuration update via Twin sync integration"""
        config_loader = config_system['config_loader']
        twin_sync = config_system['twin_sync']
        
        # Initial config
        config_loader.data = {
            'llm': {'temperature': 0.7},
            'stt': {'language': 'ja'}
        }
        
        # Twin update
        twin_patch = {
            'llm': {
                'temperature': 0.9,
                'max_tokens': 1000
            },
            'stt': {
                'language': 'en'
            }
        }
        
        # Apply twin update
        twin_sync.apply_twin_update(twin_patch)
        
        # Verify config updated
        assert config_loader.get('llm.temperature') == 0.9
        assert config_loader.get('llm.max_tokens') == 1000
        assert config_loader.get('stt.language') == 'en'
    
    @pytest.mark.asyncio
    async def test_config_propagation_to_services(self, config_system):
        """Test configuration propagation to services integration"""
        config_loader = config_system['config_loader']
        
        # Set initial config
        config_loader.data = {
            'llm': {'model': 'gpt-3.5-turbo'},
            'conversation': {'fallback_message': 'Error occurred'}
        }
        
        # Create services with config
        with patch('infrastructure.ai.llm_client.LLMClient'):
            with patch('infrastructure.memory.memory_repository.MemoryRepository'):
                with patch('application.conversation_recovery.ConversationRecovery'):
                    with patch('application.system_prompt_builder.SystemPromptBuilder'):
                        conversation_service = ConversationService(
                            config_loader, Mock(), Mock(), Mock(), Mock()
                        )
        
        # Verify service uses config
        assert conversation_service.config.get('llm.model') == 'gpt-3.5-turbo'
        assert conversation_service.config.get('conversation.fallback_message') == 'Error occurred'
    
    @pytest.mark.asyncio
    async def test_environment_variable_override(self, config_system):
        """Test configuration override via environment variables integration"""
        config_loader = config_system['config_loader']
        
        # Base config
        config_loader.data = {
            'llm': {'model': 'gpt-3.5-turbo'},
            'api': {'timeout': 30}
        }
        
        # Environment override
        with patch.dict(os.environ, {
            'LLM_MODEL': 'gpt-4',
            'API_TIMEOUT': '60'
        }):
            # Apply env overrides
            config_loader.apply_env_overrides({
                'LLM_MODEL': 'llm.model',
                'API_TIMEOUT': 'api.timeout'
            })
            
            assert config_loader.get('llm.model') == 'gpt-4'
            assert config_loader.get('api.timeout') == 60
    
    @pytest.mark.asyncio
    async def test_config_validation_rules(self, config_system):
        """Test configuration validation rules integration"""
        config_loader = config_system['config_loader']
        
        # Valid config
        valid_config = {
            'llm': {
                'temperature': 0.5,  # 0-2 range
                'max_tokens': 500    # > 0
            },
            'audio': {
                'sample_rate': 16000,  # standard rates
                'channels': 1          # 1 or 2
            }
        }
        
        config_loader.data = valid_config
        
        # Validation checks
        assert 0 <= config_loader.get('llm.temperature') <= 2
        assert config_loader.get('llm.max_tokens') > 0
        assert config_loader.get('audio.sample_rate') in [8000, 16000, 44100, 48000]
        assert config_loader.get('audio.channels') in [1, 2]
    
    @pytest.mark.asyncio
    async def test_config_hot_reload(self, config_system):
        """Test configuration hot reload"""
        config_loader = config_system['config_loader']
        
        # Initial config
        config_loader.data = {'version': '1.0'}
        
        # Simulate config file change
        new_config = {'version': '2.0', 'feature': 'enabled'}
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(new_config)
            
            # Reload config
            config_loader.reload()
        
        assert config_loader.get('version') == '2.0'
        assert config_loader.get('feature') == 'enabled'
    
    @pytest.mark.asyncio
    async def test_config_persistence_across_restart(self, config_system):
        """Test configuration persistence across restart"""
        config_loader = config_system['config_loader']
        
        # Save config
        config_to_save = {
            'persistent': True,
            'user_preferences': {
                'voice': 'nova',
                'speed': 1.2
            }
        }
        
        with patch('builtins.open', create=True) as mock_open:
            with patch('json.dump') as mock_dump:
                config_loader.data = config_to_save
                config_loader.save_to_file('/config/config.json')
                
                mock_dump.assert_called_once()
                saved_data = mock_dump.call_args[0][0]
                assert saved_data['persistent'] is True
                assert saved_data['user_preferences']['voice'] == 'nova'
    
    @pytest.mark.asyncio
    async def test_config_schema_migration(self, config_system):
        """Test configuration schema migration"""
        config_loader = config_system['config_loader']
        
        # Old schema
        old_config = {
            'openai_model': 'gpt-3.5-turbo',  # Old format
            'speech_language': 'ja'            # Old format
        }
        
        # Migration rules
        migration_rules = {
            'openai_model': 'llm.model',
            'speech_language': 'stt.language'
        }
        
        # Apply migration
        config_loader.data = {}
        for old_key, new_key in migration_rules.items():
            if old_key in old_config:
                config_loader.set(new_key, old_config[old_key])
        
        assert config_loader.get('llm.model') == 'gpt-3.5-turbo'
        assert config_loader.get('stt.language') == 'ja'
    
    @pytest.mark.asyncio
    async def test_config_with_secrets_management(self, config_system):
        """Test configuration integration with secrets management"""
        config_loader = config_system['config_loader']
        
        # Config with secret placeholders
        config_with_secrets = {
            'api': {
                'openai_key': '${OPENAI_API_KEY}',
                'azure_key': '${AZURE_SPEECH_KEY}'
            }
        }
        
        # Mock secret resolution
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'secret-key-123',
            'AZURE_SPEECH_KEY': 'secret-key-456'
        }):
            config_loader.data = config_with_secrets
            config_loader.resolve_secrets()
            
            # Secrets should be resolved
            assert config_loader.get('api.openai_key') == 'secret-key-123'
            assert config_loader.get('api.azure_key') == 'secret-key-456'
    
    @pytest.mark.asyncio
    async def test_multi_source_config_merge(self, config_system):
        """Test configuration merge from multiple sources"""
        config_loader = config_system['config_loader']
        
        # Source 1: File
        file_config = {
            'llm': {'model': 'gpt-3.5-turbo'},
            'audio': {'sample_rate': 16000}
        }
        
        # Source 2: Twin
        twin_config = {
            'llm': {'temperature': 0.8},
            'memory': {'max_pairs': 20}
        }
        
        # Source 3: Environment
        env_config = {
            'llm': {'max_tokens': 1000}
        }
        
        # Merge all sources (priority: env > twin > file)
        config_loader.data = file_config
        config_loader.merge(twin_config)
        config_loader.merge(env_config)
        
        # Verify merged config
        assert config_loader.get('llm.model') == 'gpt-3.5-turbo'  # from file
        assert config_loader.get('llm.temperature') == 0.8         # from twin
        assert config_loader.get('llm.max_tokens') == 1000        # from env
        assert config_loader.get('audio.sample_rate') == 16000    # from file
        assert config_loader.get('memory.max_pairs') == 20        # from twin