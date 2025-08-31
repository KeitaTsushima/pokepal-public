"""
Integration tests for complete conversation flow

Tests the complete flow from user voice input to response generation and voice output.
"""
import sys
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json
from datetime import datetime

# Mock Azure IoT modules (for integration test environment)
sys.modules['azure'] = MagicMock()
sys.modules['azure.iot'] = MagicMock()
sys.modules['azure.iot.device'] = MagicMock()

from domain.conversation import ConversationConfig
from application.conversation_service import ConversationService
from application.voice_interaction_service import VoiceInteractionService
from adapters.output.audio_output import AudioOutputAdapter
from infrastructure.iot.telemetry_client import IoTTelemetryClient
from infrastructure.ai.llm_client import LLMClient
from infrastructure.ai.stt_client import STTClient
from infrastructure.ai.tts_client import TTSClient
from infrastructure.audio.vad_processor import VADProcessor
from infrastructure.audio.audio_device import AudioDevice
from infrastructure.memory.memory_repository import MemoryRepository


class TestConversationFlow:
    """Integration tests for complete conversation flow"""
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components"""
        # Infrastructure layer mocks
        audio_device = Mock(spec=AudioDevice)
        vad_processor = Mock(spec=VADProcessor)
        stt_client = Mock(spec=STTClient)
        llm_client = Mock(spec=LLMClient)
        tts_client = Mock(spec=TTSClient)
        memory_repository = Mock(spec=MemoryRepository)
        
        # Adapters layer mocks
        text_to_speech = AudioOutputAdapter(tts_client, audio_device)
        telemetry_sender = Mock(spec=IoTTelemetryClient)
        
        return {
            'audio_device': audio_device,
            'vad_processor': vad_processor,
            'stt_client': stt_client,
            'llm_client': llm_client,
            'tts_client': tts_client,
            'memory_repository': memory_repository,
            'speech_to_text': stt_client,
            'text_to_speech': text_to_speech,
            'telemetry_sender': telemetry_sender
        }
    
    @pytest.fixture
    def conversation_config(self):
        """Create conversation configuration"""
        return ConversationConfig(
            max_tokens=25000,
            default_system_prompt="You are a companion for elderly people.",
            farewell_message="I understand. Let's talk again.",
            llm_model_name="gpt-4o-mini",
            tokenizer_encoding_method="cl100k_base"
        )
    
    @pytest.fixture
    def services(self, mock_components, conversation_config):
        """Build service layer"""
        conversation_service = ConversationService(
            config=conversation_config,
            ai_client=mock_components['llm_client'],
            memory_repository=mock_components['memory_repository'],
            telemetry_adapter=mock_components['telemetry_sender']
        )
        
        voice_service = VoiceInteractionService(
            conversation_service=conversation_service,
            audio_capture=mock_components['vad_processor'],
            speech_to_text=mock_components['speech_to_text'],
            audio_output=mock_components['text_to_speech']
        )
        
        return {
            'conversation': conversation_service,
            'voice': voice_service,
            'mocks': mock_components
        }
    
    def test_normal_conversation_flow(self, services):
        """Test normal conversation flow"""
        mocks = services['mocks']
        voice_service = services['voice']
        
        # Mock voice input setup
        mocks['vad_processor'].wait_for_speech.return_value = "/tmp/audio1.wav"
        mocks['stt_client'].transcribe.return_value = "Hello"
        
        # Mock AI response setup
        mocks['llm_client'].generate_response.return_value = "Hello! It's nice weather today."
        
        # Mock TTS output setup
        mocks['tts_client'].synthesize.return_value = "/tmp/response1.wav"
        
        # Execute conversation processing
        voice_service.initialize()
        result = voice_service.process_conversation()
        
        # Verify: each component was called correctly
        mocks['vad_processor'].wait_for_speech.assert_called_once()
        mocks['stt_client'].transcribe.assert_called_once_with("/tmp/audio1.wav")
        mocks['llm_client'].generate_response.assert_called_once()
        mocks['tts_client'].synthesize.assert_called_once()
        mocks['audio_device'].play.assert_called()
        mocks['telemetry_sender'].send_conversation.assert_called_once()
        
        # Check continuation flag
        assert result is True
    
    def test_no_voice_to_sleep_mode_flow(self, services):
        """Flow transition from no voice to sleep mode"""
        mocks = services['mocks']
        voice_service = services['voice']
        conversation_service = services['conversation']
        
        # 5 consecutive no voice
        mocks['vad_processor'].wait_for_speech.return_value = None
        
        # Test sleep mode transition
        for i in range(5):
            result = voice_service.process_conversation()
            assert result is True
        
        # Enter sleep mode on 5th time
        assert conversation_service.is_sleeping() is True
        
        # Response during sleep mode
        # Note: Actual path is obtained from config
        mocks['audio_device'].play.assert_called()
    
    def test_exit_command_flow(self, services):
        """Exit command flow"""
        mocks = services['mocks']
        voice_service = services['voice']
        
        # Exit command input
        mocks['vad_processor'].wait_for_speech.return_value = "/tmp/audio_exit.wav"
        mocks['stt_client'].transcribe.return_value = "Goodbye"
        
        # Execute conversation processing
        result = voice_service.process_conversation()
        
        # Verify: exit flag
        assert result is False
        
        # Farewell message is played
        # Note: Actual path is obtained from config
        mocks['audio_device'].play.assert_called()
    
    def test_conversation_with_memory_flow(self, services):
        """Conversation flow including memory system"""
        mocks = services['mocks']
        voice_service = services['voice']
        
        # Mock memory data
        memory_data = {
            "short_term": [
                {"date": "2025-07-01", "summary": "Talked about garden flowers with Hanako"}
            ],
            "long_term": [
                {"summary": "Likes flowers, especially growing roses"}
            ]
        }
        mocks['memory_repository'].get_latest_memory.return_value = memory_data
        
        # User input
        mocks['vad_processor'].wait_for_speech.return_value = "/tmp/audio2.wav"
        mocks['stt_client'].transcribe.return_value = "Let's talk about flowers again today"
        
        # AI response (response based on memory)
        mocks['llm_client'].generate_response.return_value = (
            "That's nice! How are the garden roses you mentioned yesterday?"
        )
        
        # TTS output
        mocks['tts_client'].synthesize.return_value = "/tmp/response2.wav"
        
        # Execute conversation processing
        voice_service.initialize()
        result = voice_service.process_conversation()
        
        # Verify: memory is loaded and included in system prompt
        call_args = mocks['llm_client'].generate_response.call_args
        messages = call_args[0][0]
        system_message = messages[0]
        assert "Talked about garden flowers with Hanako" in system_message['content']
        assert "Likes flowers, especially growing roses" in system_message['content']
    
    def test_error_recovery_flow(self, services):
        """Error recovery flow"""
        mocks = services['mocks']
        voice_service = services['voice']
        
        # Error in voice recognition
        mocks['vad_processor'].wait_for_speech.return_value = "/tmp/audio3.wav"
        mocks['stt_client'].transcribe.side_effect = Exception("Transcription error")
        
        # Error handling
        result = voice_service.process_conversation()
        
        # Error message is played
        # Note: Actual path is obtained from config
        mocks['audio_device'].play.assert_called()
        
        # Conversation continues
        assert result is True
    
    def test_full_conversation_sequence(self, services):
        """Multi-turn conversation sequence"""
        mocks = services['mocks']
        voice_service = services['voice']
        
        # Define conversation sequence
        conversation_sequence = [
            {
                "user": "Good morning",
                "assistant": "Good morning! It looks like it will be a good day today.",
                "audio": "/tmp/audio_morning.wav",
                "response_audio": "/tmp/response_morning.wav"
            },
            {
                "user": "The weather is nice today",
                "assistant": "It really is nice weather. Will you go for a walk?",
                "audio": "/tmp/audio_weather.wav",
                "response_audio": "/tmp/response_weather.wav"
            },
            {
                "user": "Yes, maybe I'll walk to the park",
                "assistant": "That's nice! The cherry blossoms in the park might already be blooming.",
                "audio": "/tmp/audio_park.wav",
                "response_audio": "/tmp/response_park.wav"
            }
        ]
        
        # Initialize
        voice_service.initialize()
        
        # Execute each turn
        for i, turn in enumerate(conversation_sequence):
            # Mock setup
            mocks['vad_processor'].wait_for_speech.return_value = turn["audio"]
            mocks['stt_client'].transcribe.return_value = turn["user"]
            mocks['llm_client'].generate_response.return_value = turn["assistant"]
            mocks['tts_client'].synthesize.return_value = turn["response_audio"]
            
            # Conversation processing
            result = voice_service.process_conversation()
            assert result is True
            
            # Verify
            mocks['stt_client'].transcribe.assert_called_with(turn["audio"])
            mocks['tts_client'].synthesize.assert_called_with(turn["assistant"])
            
            # Confirm telemetry sending
            telemetry_call = mocks['telemetry_sender'].send_conversation.call_args_list[i]
            sent_data = telemetry_call[0][0]
            assert sent_data['user_message'] == turn["user"]
            assert sent_data['ai_response'] == turn["assistant"]
    
    def test_sleep_mode_wake_up_flow(self, services):
        """Wake up flow from sleep mode"""
        mocks = services['mocks']
        voice_service = services['voice']
        conversation_service = services['conversation']
        
        # Enter sleep mode
        conversation_service._is_sleeping = True
        
        # Wake up with keyword
        mocks['vad_processor'].wait_for_speech.return_value = "/tmp/audio_wake.wav"
        mocks['stt_client'].transcribe.return_value = "Hey, listen"
        mocks['llm_client'].generate_response.return_value = "Yes, I'm listening."
        mocks['tts_client'].synthesize.return_value = "/tmp/response_wake.wav"
        
        # 会話処理
        result = voice_service.process_conversation()
        
        # Return from sleep mode
        assert conversation_service.is_sleeping() is False
        assert result is True
        
        # Normal response is generated
        mocks['llm_client'].generate_response.assert_called_once()