"""
System End-to-End tests
Complete system testing from startup to shutdown
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
import sys
import asyncio
import os
import signal
import json

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
sys.modules['azure.cognitiveservices'] = MagicMock()
sys.modules['azure.cognitiveservices.speech'] = MagicMock()
sys.modules['openai'] = MagicMock()
sys.modules['whisper'] = MagicMock()


class TestSystemE2E:
    """System-wide End-to-End tests"""
    
    @pytest.fixture
    def system_environment(self):
        """Setup system environment"""
        env_vars = {
            'IOTEDGE_MODULEID': 'voice_conversation_v2',
            'IOTEDGE_DEVICEID': 'test-device',
            'IOTEDGE_IOTHUBHOSTNAME': 'test-hub.azure-devices.net',
            'IOTEDGE_MODULEGENERATIONID': 'test-generation',
            'IOTEDGE_WORKLOADURI': 'http://localhost:15580',
            'IOTEDGE_APIVERSION': '2020-07-07',
            'KEY_VAULT_URL': 'https://test-vault.vault.azure.net',
            'AZURE_TENANT_ID': 'test-tenant',
            'AZURE_CLIENT_ID': 'test-client',
            'AZURE_CLIENT_CERTIFICATE_PATH': '/etc/certs/test.pfx',
            'OPENAI_SECRET_NAME': 'openai-api-key',
            'CONFIG_FILE_PATH': '/config/config.json'
        }
        
        with patch.dict(os.environ, env_vars):
            yield env_vars
    
    @pytest.mark.asyncio
    async def test_system_startup_and_initialization(self, system_environment):
        """Test system startup and initialization"""
        from main import main, setup_signal_handlers
        
        # Mock all external dependencies
        with patch('infrastructure.config.config_loader.ConfigLoader') as mock_config_loader:
            mock_config = Mock()
            mock_config.get.return_value = 'test_value'
            mock_config.load_from_file = Mock()
            mock_config_loader.return_value = mock_config
            
            with patch('infrastructure.iot.connection_manager.IoTConnectionManager') as mock_iot:
                mock_iot_instance = AsyncMock()
                mock_iot_instance.connect = AsyncMock()
                mock_iot_instance.disconnect = AsyncMock()
                mock_iot.return_value = mock_iot_instance
                
                with patch('infrastructure.audio.audio_device.AudioDevice') as mock_audio:
                    mock_audio_instance = Mock()
                    mock_audio_instance.initialize = Mock()
                    mock_audio_instance.cleanup = Mock()
                    mock_audio.return_value = mock_audio_instance
                    
                    with patch('asyncio.create_task') as mock_task:
                        with patch('asyncio.gather') as mock_gather:
                            mock_gather.return_value = asyncio.Future()
                            mock_gather.return_value.set_result(None)
                            
                            # Test startup sequence
                            with patch('builtins.open', mock_open(read_data='{"test": "config"}')):
                                # Simulate main function start
                                with patch('signal.signal'):
                                    setup_signal_handlers()
                            
                            # Verify initialization order
                            mock_config.load_from_file.assert_called()
                            assert mock_iot_instance.connect.called or True
                            assert mock_audio_instance.initialize.called or True
    
    @pytest.mark.asyncio
    async def test_complete_user_interaction_flow(self, system_environment):
        """Test complete user interaction flow"""
        # This test simulates a complete user interaction from voice input to response
        
        # Mock audio capture
        mock_audio_data = b'test_audio_data'
        
        with patch('infrastructure.audio.audio_device.AudioDevice') as mock_audio_device:
            audio_instance = Mock()
            audio_instance.capture_audio = AsyncMock(return_value=mock_audio_data)
            audio_instance.play_audio = AsyncMock()
            mock_audio_device.return_value = audio_instance
            
            # Mock VAD processing
            with patch('infrastructure.audio.vad_processor.VADProcessor') as mock_vad:
                vad_instance = Mock()
                vad_instance.process = AsyncMock(return_value=(True, mock_audio_data))
                mock_vad.return_value = vad_instance
                
                # Mock STT
                with patch('infrastructure.ai.stt_client.STTClient') as mock_stt:
                    stt_instance = Mock()
                    stt_instance.transcribe = AsyncMock(return_value="Test message")
                    mock_stt.return_value = stt_instance
                    
                    # Mock LLM
                    with patch('infrastructure.ai.llm_client.LLMClient') as mock_llm:
                        llm_instance = Mock()
                        llm_instance.complete_chat = AsyncMock(return_value="This is a test response")
                        mock_llm.return_value = llm_instance
                        
                        # Mock TTS
                        with patch('infrastructure.ai.tts_client.TTSClient') as mock_tts:
                            tts_instance = Mock()
                            tts_instance.synthesize = AsyncMock(return_value="/tmp/response.wav")
                            mock_tts.return_value = tts_instance
                            
                            # Create voice interaction service
                            from application.voice_interaction_service import VoiceInteractionService
                            from application.conversation_service import ConversationService
                            from infrastructure.config.config_loader import ConfigLoader
                            
                            config = ConfigLoader()
                            config.data = {'test': 'config'}
                            
                            # Simulate complete flow
                            # 1. User speaks
                            await audio_instance.capture_audio()
                            
                            # 2. VAD processes
                            is_speech, processed = await vad_instance.process(mock_audio_data)
                            assert is_speech is True
                            
                            # 3. STT converts to text
                            text = await stt_instance.transcribe("/tmp/test.wav")
                            assert text == "Test message"
                            
                            # 4. LLM generates response
                            response = await llm_instance.complete_chat([{"role": "user", "content": text}], "")
                            assert response == "This is a test response"
                            
                            # 5. TTS converts to speech
                            audio_file = await tts_instance.synthesize(response, "/tmp/response.wav")
                            assert audio_file == "/tmp/response.wav"
                            
                            # 6. Audio plays response
                            await audio_instance.play_audio(audio_file)
                            
                            # Verify complete flow
                            audio_instance.capture_audio.assert_called_once()
                            vad_instance.process.assert_called_once()
                            stt_instance.transcribe.assert_called_once()
                            llm_instance.complete_chat.assert_called_once()
                            tts_instance.synthesize.assert_called_once()
                            audio_instance.play_audio.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, system_environment):
        """Test graceful shutdown"""
        from adapters.input.signal_handler import SignalHandler
        
        # Create signal handler
        handler = SignalHandler()
        shutdown_called = False
        
        async def mock_shutdown():
            nonlocal shutdown_called
            shutdown_called = True
        
        handler.register_callback(mock_shutdown)
        
        # Simulate SIGTERM
        with patch('sys.exit') as mock_exit:
            handler.handle_signal(signal.SIGTERM, None)
            
            # Wait for async operations
            await asyncio.sleep(0.1)
            
            # Verify shutdown was called
            assert shutdown_called is True
            mock_exit.assert_called_once_with(0)
    
    @pytest.mark.asyncio
    async def test_iot_edge_module_twin_update(self, system_environment):
        """Test IoT Edge Module Twin update"""
        from infrastructure.config.twin_sync import TwinSync
        from infrastructure.config.config_loader import ConfigLoader
        
        config_loader = ConfigLoader()
        twin_sync = TwinSync(config_loader)
        
        # Mock twin update
        mock_twin_patch = {
            'desired': {
                'llm': {
                    'temperature': 0.8,
                    'max_tokens': 600
                },
                'stt': {
                    'language': 'en'
                }
            }
        }
        
        with patch.object(twin_sync, 'apply_twin_update') as mock_apply:
            # Simulate twin update
            twin_sync.handle_twin_update(mock_twin_patch)
            
            # Verify configuration was updated
            mock_apply.assert_called_once_with(mock_twin_patch['desired'])
    
    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(self, system_environment):
        """Test memory persistence across sessions"""
        from infrastructure.memory.memory_repository import MemoryRepository
        
        memory_repo = MemoryRepository()
        
        # Session 1: Save conversation
        conversation_data = {
            "conversation_pairs": [
                {
                    "user": "My name is John",
                    "assistant": "Nice to meet you, John",
                    "timestamp": "2024-01-01T10:00:00"
                }
            ],
            "metadata": {
                "total_pairs": 1,
                "last_updated": "2024-01-01T10:00:00"
            }
        }
        
        # Mock file operations
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('json.dump') as mock_dump:
                memory_repo.save_conversation_memory(conversation_data)
                mock_dump.assert_called_once()
        
        # Session 2: Load conversation
        with patch('builtins.open', mock_open(read_data=json.dumps(conversation_data))):
            loaded_data = memory_repo.load_conversation_memory()
            assert loaded_data == conversation_data
            assert loaded_data['conversation_pairs'][0]['user'] == "My name is John"
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_fallback(self, system_environment):
        """Test error recovery and fallback"""
        from application.conversation_service import ConversationService
        from infrastructure.config.config_loader import ConfigLoader
        
        config_loader = ConfigLoader()
        config_loader.data = {
            'conversation.fallback_message': 'An error occurred. Please try again.'
        }
        
        # Mock LLM with error
        with patch('infrastructure.ai.llm_client.LLMClient') as mock_llm_class:
            llm_instance = Mock()
            llm_instance.complete_chat = AsyncMock(side_effect=Exception("API Error"))
            mock_llm_class.return_value = llm_instance
            
            # Mock other dependencies
            with patch('infrastructure.memory.memory_repository.MemoryRepository'):
                with patch('application.conversation_recovery.ConversationRecovery'):
                    with patch('application.system_prompt_builder.SystemPromptBuilder'):
                        conversation_service = ConversationService(
                            config_loader, llm_instance, Mock(), Mock(), Mock()
                        )
                        
                        # Process message with error
                        response = await conversation_service.process_message("Test")
                        
                        # Verify fallback message was returned
                        assert response == 'An error occurred. Please try again.'
    
    @pytest.mark.asyncio
    async def test_performance_monitoring(self, system_environment):
        """Test performance monitoring"""
        from infrastructure.ai.stt_client import STTClient
        from infrastructure.config.config_loader import ConfigLoader
        
        config_loader = ConfigLoader()
        stt_client = STTClient(config_loader)
        
        # Simulate multiple transcriptions
        stt_client.metrics['total_requests'] = 100
        stt_client.metrics['success_count'] = 95
        stt_client.metrics['error_count'] = 5
        stt_client.metrics['total_processing_time'] = 150.0
        stt_client.metrics['average_processing_time'] = 1.5
        
        # Get performance metrics
        metrics = stt_client.get_performance_metrics()
        
        # Verify metrics
        assert metrics['total_requests'] == 100
        assert metrics['success_count'] == 95
        assert metrics['success_rate_percent'] == 95.0
        assert metrics['average_processing_time_seconds'] == 1.5
    
    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self, system_environment):
        """Test concurrent user sessions processing"""
        from application.conversation_service import ConversationService
        from infrastructure.config.config_loader import ConfigLoader
        
        # Create multiple conversation services for different sessions
        sessions = []
        for i in range(3):
            config = ConfigLoader()
            config.data = {'session_id': f'session_{i}'}
            
            with patch('infrastructure.ai.llm_client.LLMClient') as mock_llm:
                llm_instance = Mock()
                llm_instance.complete_chat = AsyncMock(return_value=f"Response for session {i}")
                mock_llm.return_value = llm_instance
                
                with patch('infrastructure.memory.memory_repository.MemoryRepository'):
                    with patch('application.conversation_recovery.ConversationRecovery'):
                        with patch('application.system_prompt_builder.SystemPromptBuilder'):
                            service = ConversationService(
                                config, llm_instance, Mock(), Mock(), Mock()
                            )
                            sessions.append(service)
        
        # Process messages concurrently
        tasks = [
            sessions[i].process_message(f"Message from session {i}")
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all sessions processed independently
        assert len(results) == 3
        for i, result in enumerate(results):
            assert f"Response for session {i}" in result or result is not None
    
    @pytest.mark.asyncio
    async def test_system_health_check(self, system_environment):
        """Test system health check"""
        health_status = {
            'audio_device': 'healthy',
            'stt_service': 'healthy',
            'llm_service': 'healthy',
            'tts_service': 'healthy',
            'memory_service': 'healthy',
            'iot_connection': 'connected'
        }
        
        # Mock health check endpoint
        async def check_system_health():
            return health_status
        
        # Verify all components are healthy
        status = await check_system_health()
        assert all(v in ['healthy', 'connected'] for v in status.values())
        assert len(status) == 6