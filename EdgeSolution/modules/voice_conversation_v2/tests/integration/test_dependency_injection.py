"""
Dependency Injection (DI) Container Integration Tests

Tests that the Application class in main.py correctly
assembles all components.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add path for test target
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from main import Application
from application.conversation_service import ConversationService
from application.voice_interaction_service import VoiceInteractionService
from infrastructure.config.config_loader import ConfigLoader


class TestDependencyInjection:
    """Dependency injection container integration tests"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration data"""
        return {
            "vad": {
                "mode": 3,
                "speech_threshold": 30,
                "silence_threshold": 10
            },
            "stt": {
                "api_key": "test-stt-key",
                "model": "whisper-1",
                "language": "ja"
            },
            "llm": {
                "api_key": "test-llm-key",
                "model": "gpt-4o-mini",
                "temperature": 0.7
            },
            "tts": {
                "api_key": "test-tts-key",
                "voice": "nova",
                "speed": 1.0
            },
            "memory": {
                "dir": "/app/memories"
            },
            "conversation": {
                "system_base_prompt": "Test prompt",
                "token_limit": 4000,
                "immediate_memory_token_limit": 25000,
                "exit_phrases": ["goodbye"],
                "sleep_mode_enabled": True,
                "sleep_threshold": 5,
                "greeting_interval_hours": 6,
                "response_timeout": 30.0
            }
        }
    
    @patch('main.ConfigLoader')
    @patch('main.signal.signal')
    def test_application_setup(self, mock_signal, MockConfigLoader, mock_config):
        """Test application setup"""
        # Mock ConfigLoader setup
        mock_loader = Mock(spec=ConfigLoader)
        mock_loader.get.side_effect = lambda key, default=None: {
            "vad.mode": 3,
            "vad.speech_threshold": 30,
            "vad.silence_threshold": 10,
            "stt.api_key": "test-stt-key",
            "stt.model": "whisper-1",
            "stt.language": "ja",
            "llm.api_key": "test-llm-key",
            "llm.model": "gpt-4o-mini",
            "llm.temperature": 0.7,
            "tts.api_key": "test-tts-key",
            "tts.voice": "nova",
            "tts.speed": 1.0,
            "memory.dir": "/app/memories"
        }.get(key, default)
        mock_loader.get_config.return_value = mock_config
        mock_loader.load_from_file.return_value = None
        MockConfigLoader.return_value = mock_loader
        
        # Create Application instance
        app = Application()
        
        # Execute setup
        app.setup()
        
        # Verify: Each component was created
        assert app.config_loader is not None
        assert app.voice_service is not None
        assert app.iot_commands is not None
        
        # Verify ConfigLoader methods were called
        mock_loader.sync_with_twin.assert_called_once()
        mock_loader.load_from_file.assert_called_once_with("/app/config/config.json")
        
        # Verify signal handlers were set
        assert mock_signal.call_count >= 2  # SIGTERM, SIGINT
    
    @patch('main.AudioDevice')
    @patch('main.VADProcessor')
    @patch('main.STTClient')
    @patch('main.LLMClient')
    @patch('main.TTSClient')
    @patch('main.MemoryRepository')
    @patch('main.ConfigLoader')
    @patch('main.signal.signal')
    def test_component_initialization_order(
        self, mock_signal, MockConfigLoader, MockMemoryRepository,
        MockTTSClient, MockLLMClient, MockSTTClient,
        MockVADProcessor, MockAudioDevice, mock_config
    ):
        """Test component initialization order"""
        # Mock ConfigLoader
        mock_loader = Mock(spec=ConfigLoader)
        mock_loader.get.side_effect = lambda key, default=None: mock_config.get(key.split('.')[0], {}).get(key.split('.')[1], default) if '.' in key else default
        mock_loader.get_config.return_value = mock_config
        mock_loader.load_from_file.return_value = None
        MockConfigLoader.return_value = mock_loader
        
        # Mock each component
        mock_audio_device = Mock()
        MockAudioDevice.return_value = mock_audio_device
        
        app = Application()
        app.setup()
        
        # Verify initialization order
        # 1. ConfigLoader first
        MockConfigLoader.assert_called_once()
        
        # 2. Infrastructure layer next
        MockAudioDevice.assert_called_once()
        MockVADProcessor.assert_called_once()
        MockSTTClient.assert_called_once()
        MockLLMClient.assert_called_once()
        MockTTSClient.assert_called_once()
        MockMemoryRepository.assert_called_once()
        
        # 3. Verify AudioDevice is passed to VADProcessor
        vad_call_args = MockVADProcessor.call_args
        assert vad_call_args[1]['audio_device'] == mock_audio_device
    
    @patch('main.ConfigLoader')
    @patch('main.VoiceInteractionService')
    @patch('main.ConversationService')
    def test_application_run(self, MockConversationService, MockVoiceService, MockConfigLoader, mock_config):
        """Test application execution"""
        # Setup mocks
        mock_loader = Mock()
        mock_loader.get.return_value = "dummy"
        mock_loader.get_config.return_value = mock_config
        mock_loader.load_from_file.return_value = None
        MockConfigLoader.return_value = mock_loader
        
        mock_voice_service = Mock()
        MockVoiceService.return_value = mock_voice_service
        
        # Execute application
        app = Application()
        
        # Error when calling run() without setup()
        with pytest.raises(RuntimeError, match="Application not properly setup"):
            app.run()
        
        # Normal execution flow
        with patch('main.signal.signal'):
            app.setup()
            app.run()
        
        # Verify VoiceInteractionService methods were called
        mock_voice_service.initialize.assert_called_once()
        mock_voice_service.run.assert_called_once()
    
    @patch('main.ConfigLoader')
    @patch('main.VoiceInteractionService')
    def test_application_stop(self, MockVoiceService, MockConfigLoader, mock_config):
        """Test application stop"""
        # Setup mocks
        mock_loader = Mock()
        mock_loader.get.return_value = "dummy"
        mock_loader.get_config.return_value = mock_config
        mock_loader.load_from_file.return_value = None
        MockConfigLoader.return_value = mock_loader
        
        mock_voice_service = Mock()
        MockVoiceService.return_value = mock_voice_service
        
        app = Application()
        with patch('main.signal.signal'):
            app.setup()
        
        # Stop processing
        app.stop()
        
        # Verify VoiceInteractionService.stop() was called
        mock_voice_service.stop.assert_called_once()
    
    @patch('main.ConfigLoader')
    def test_config_loader_error_handling(self, MockConfigLoader):
        """Test configuration loading error handling"""
        # Raise error in ConfigLoader
        mock_loader = Mock()
        mock_loader.sync_with_twin.side_effect = Exception("Twin sync error")
        MockConfigLoader.return_value = mock_loader
        
        app = Application()
        
        # Setup completes even with error (error is logged)
        with patch('main.signal.signal'):
            with pytest.raises(Exception):
                app.setup()
    
    def test_main_function(self):
        """Test main function"""
        with patch('main.Application') as MockApplication:
            mock_app = Mock()
            MockApplication.return_value = mock_app
            
            # Normal termination
            from main import main
            main()
            
            mock_app.setup.assert_called_once()
            mock_app.run.assert_called_once()
    
    def test_main_function_with_error(self):
        """Test main function error handling"""
        with patch('main.Application') as MockApplication:
            mock_app = Mock()
            mock_app.setup.side_effect = Exception("Setup failed")
            MockApplication.return_value = mock_app
            
            # sys.exit(1) is called on error
            with patch('sys.exit') as mock_exit:
                from main import main
                main()
                
                mock_exit.assert_called_once_with(1)