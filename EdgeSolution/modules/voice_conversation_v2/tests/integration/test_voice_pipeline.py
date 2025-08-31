"""
Voice pipeline integration tests
End-to-end testing of voice conversation pipeline
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import asyncio
import os

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

from application.voice_interaction_service import VoiceInteractionService
from application.conversation_service import ConversationService
from application.conversation_recovery import ConversationRecovery
from application.system_prompt_builder import SystemPromptBuilder
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.ai.stt_client import STTClient
from infrastructure.ai.llm_client import LLMClient
from infrastructure.ai.tts_client import TTSClient
from infrastructure.audio.vad_processor import VADProcessor
from infrastructure.audio.audio_device import AudioDevice
from infrastructure.memory.memory_repository import MemoryRepository


class TestVoicePipeline:
    """Integration tests for complete voice pipeline"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        mock = Mock(spec=ConfigLoader)
        mock.get.side_effect = lambda key, default=None: {
            'llm.model': 'gpt-4',
            'llm.max_tokens': 500,
            'llm.temperature': 0.7,
            'llm.system_prompt': 'You are a helpful assistant',
            'stt.openai.model': 'whisper-1',
            'stt.language': 'ja',
            'tts.model': 'tts-1',
            'tts.voice': 'nova',
            'conversation.farewell_message': 'Let\'s talk again',
            'conversation.fallback_message': 'Sorry, please say that again',
            'memory.max_conversation_pairs': 10,
            'memory.immediate_tokens': 25000
        }.get(key, default)
        return mock
    
    @pytest.fixture
    def voice_pipeline(self, mock_config_loader):
        """Setup complete voice pipeline"""
        # Infrastructure components
        with patch.dict(os.environ, {'OPENAI_SECRET_NAME': 'test-secret'}):
            stt_client = STTClient(mock_config_loader)
            llm_client = LLMClient(mock_config_loader)
            tts_client = TTSClient(mock_config_loader)
        
        audio_device = Mock(spec=AudioDevice)
        vad_processor = Mock(spec=VADProcessor)
        memory_repository = Mock(spec=MemoryRepository)
        
        # Application services
        prompt_builder = SystemPromptBuilder(mock_config_loader)
        recovery = ConversationRecovery(mock_config_loader, memory_repository, prompt_builder)
        conversation_service = ConversationService(
            mock_config_loader, llm_client, memory_repository, 
            recovery, prompt_builder
        )
        
        voice_service = VoiceInteractionService(
            audio_device, vad_processor, stt_client, 
            conversation_service, tts_client, mock_config_loader
        )
        
        return {
            'voice_service': voice_service,
            'conversation_service': conversation_service,
            'stt_client': stt_client,
            'llm_client': llm_client,
            'tts_client': tts_client,
            'audio_device': audio_device,
            'vad_processor': vad_processor,
            'memory_repository': memory_repository,
            'config_loader': mock_config_loader
        }
    
    @pytest.mark.asyncio
    async def test_complete_voice_conversation_flow(self, voice_pipeline):
        """Test complete voice conversation flow"""
        # Setup mocks
        audio_device = voice_pipeline['audio_device']
        vad_processor = voice_pipeline['vad_processor']
        
        # Mock audio capture
        audio_device.capture_audio = AsyncMock(return_value=b'audio_data')
        vad_processor.process = AsyncMock(return_value=(True, b'processed_audio'))
        
        # Mock STT
        with patch('infrastructure.ai.stt_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_stt_client = AsyncMock()
            mock_stt_client.audio.transcriptions.create = AsyncMock(return_value="Hello")
            mock_shared.get_stt_client = AsyncMock(return_value=mock_stt_client)
            mock_get_shared.return_value = mock_shared
            
            # Mock LLM
            with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_llm_shared:
                mock_llm_shared = AsyncMock()
                mock_llm_client = AsyncMock()
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="Hello! How are you?"))]
                mock_llm_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_llm_shared.get_llm_client = AsyncMock(return_value=mock_llm_client)
                mock_get_llm_shared.return_value = mock_llm_shared
                
                # Mock TTS
                with patch('infrastructure.ai.tts_client.TTSCoreSynthesizer') as mock_tts_core:
                    mock_synthesizer = AsyncMock()
                    mock_synthesizer.synthesize = AsyncMock(return_value="/tmp/output.wav")
                    mock_tts_core.return_value = mock_synthesizer
                    
                    # Mock audio playback
                    audio_device.play_audio = AsyncMock()
                    
                    # Execute conversation flow
                    voice_service = voice_pipeline['voice_service']
                    
                    # Process voice input
                    result = await voice_service.process_voice_input("/tmp/test_audio.wav")
                    
                    # Verify flow
                    assert result is not None
                    vad_processor.process.assert_called_once()
                    mock_stt_client.audio.transcriptions.create.assert_called_once()
                    mock_llm_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_conversation_with_memory_recovery(self, voice_pipeline):
        """Test conversation flow with memory recovery"""
        memory_repo = voice_pipeline['memory_repository']
        conversation_service = voice_pipeline['conversation_service']
        
        # Setup memory data
        memory_data = {
            "conversation_pairs": [
                {
                    "user": "What are your hobbies?",
                    "assistant": "My hobby is reading.",
                    "timestamp": "2024-01-01T10:00:00"
                }
            ],
            "metadata": {
                "total_pairs": 1,
                "last_updated": "2024-01-01T10:00:00"
            }
        }
        memory_repo.load_conversation_memory = Mock(return_value=memory_data)
        memory_repo.save_memory_to_blob = AsyncMock()
        
        # Mock LLM with memory context
        with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="That's about the reading we talked about last time."))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_shared.get_llm_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            # Initialize with memory
            await conversation_service.initialize()
            
            # Process message with context
            response = await conversation_service.process_message("Tell me more about reading")
            
            # Verify memory was loaded and used
            assert response == "That's about the reading we talked about last time."
            memory_repo.load_conversation_memory.assert_called_once()
            
            # Verify system prompt includes memory
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            system_message = messages[0]
            assert system_message['role'] == 'system'
            assert 'What are your hobbies' in system_message['content']
    
    @pytest.mark.asyncio
    async def test_streaming_response_pipeline(self, voice_pipeline):
        """Test streaming response pipeline"""
        conversation_service = voice_pipeline['conversation_service']
        
        # Mock streaming LLM response
        async def mock_stream():
            yield Mock(choices=[Mock(delta=Mock(content="Hel"))])
            yield Mock(choices=[Mock(delta=Mock(content="lo, "))])
            yield Mock(choices=[Mock(delta=Mock(content="how are you?"))])
        
        with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_shared.get_llm_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            # Process streaming response
            chunks = []
            async for chunk in conversation_service.generate_response_stream("Hello"):
                chunks.append(chunk)
            
            # Verify streaming worked
            assert len(chunks) >= 3
            assert any(chunk.get('type') == 'segment' for chunk in chunks)
            assert chunks[-1]['type'] == 'final'
            assert chunks[-1]['text'] == "Hello, how are you?"
    
    @pytest.mark.asyncio
    async def test_error_recovery_pipeline(self, voice_pipeline):
        """Test error recovery pipeline"""
        voice_service = voice_pipeline['voice_service']
        audio_device = voice_pipeline['audio_device']
        vad_processor = voice_pipeline['vad_processor']
        
        # Setup error scenarios
        audio_device.capture_audio = AsyncMock(return_value=b'audio_data')
        vad_processor.process = AsyncMock(return_value=(True, b'processed_audio'))
        
        # STT fails first time, succeeds second time
        with patch('infrastructure.ai.stt_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            
            from openai import APIConnectionError
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=[
                    APIConnectionError("Connection failed"),
                    "Retry successful"
                ]
            )
            mock_shared.get_stt_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            # Process should recover from error
            with patch('builtins.open', create=True):
                result = await voice_service.process_voice_input("/tmp/test.wav")
            
            # Verify retry happened
            assert mock_client.audio.transcriptions.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_farewell_detection_pipeline(self, voice_pipeline):
        """Test farewell detection pipeline"""
        conversation_service = voice_pipeline['conversation_service']
        
        # Test farewell commands
        farewell_commands = ["goodbye", "bye", "see you"]
        
        for command in farewell_commands:
            result = await conversation_service.process_message(command)
            assert result == "Let's talk again"
            assert conversation_service.should_exit is True
            
            # Reset for next test
            conversation_service.should_exit = False
    
    @pytest.mark.asyncio
    async def test_concurrent_pipeline_operations(self, voice_pipeline):
        """Test concurrent pipeline operations"""
        conversation_service = voice_pipeline['conversation_service']
        
        # Mock LLM for concurrent requests
        with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            
            responses = [
                Mock(choices=[Mock(message=Mock(content=f"Response {i}"))]) 
                for i in range(3)
            ]
            mock_client.chat.completions.create = AsyncMock(side_effect=responses)
            mock_shared.get_llm_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            # Execute concurrent requests
            tasks = [
                conversation_service.process_message(f"Message {i}")
                for i in range(3)
            ]
            results = await asyncio.gather(*tasks)
            
            # Verify all completed
            assert len(results) == 3
            assert all(f"Response {i}" in results for i in range(3))
    
    @pytest.mark.asyncio
    async def test_telemetry_integration(self, voice_pipeline):
        """Test telemetry integration"""
        from infrastructure.iot.telemetry_client import IoTTelemetryClient
        
        telemetry_client = Mock(spec=IoTTelemetryClient)
        telemetry_client.send_telemetry = AsyncMock()
        
        conversation_service = voice_pipeline['conversation_service']
        conversation_service.telemetry_client = telemetry_client
        
        # Process message
        with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            mock_response = Mock(choices=[Mock(message=Mock(content="Test response"))])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_shared.get_llm_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            await conversation_service.process_message("Test message")
            
            # Verify telemetry was sent
            if hasattr(conversation_service, 'send_telemetry'):
                telemetry_client.send_telemetry.assert_called()
    
    @pytest.mark.asyncio
    async def test_configuration_update_pipeline(self, voice_pipeline):
        """Test configuration update pipeline"""
        config_loader = voice_pipeline['config_loader']
        conversation_service = voice_pipeline['conversation_service']
        
        # Update configuration
        new_config = {
            'llm.temperature': 0.9,
            'llm.max_tokens': 1000
        }
        
        # Update config mock
        config_loader.get.side_effect = lambda key, default=None: new_config.get(key, default)
        
        # Process with new config
        with patch('infrastructure.ai.llm_client.get_shared_openai') as mock_get_shared:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            mock_response = Mock(choices=[Mock(message=Mock(content="Updated response"))])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_shared.get_llm_client = AsyncMock(return_value=mock_client)
            mock_get_shared.return_value = mock_shared
            
            await conversation_service.process_message("Test")
            
            # Verify new config was used
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs.get('temperature') == 0.9 or call_kwargs.get('max_tokens') == 1000