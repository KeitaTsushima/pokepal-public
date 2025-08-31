"""
Unit tests for ConversationService
Tests business logic layer conversation management service
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
import warnings
from datetime import datetime

from application.conversation_service import ConversationService
from domain.conversation import Conversation, ConversationConfig, MessageRole, ConversationStatus


class TestConversationService:
    """Test class for ConversationService"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader for testing"""
        config_loader = Mock()
        config_loader.get.side_effect = lambda key, default=None: {
            'memory.immediate_tokens': 25000,
            'llm.system_prompt': "You are a companion for elderly people.",
            'conversation.farewell_message': "I understand. Let's talk again.",
            'llm.model': "gpt-4o-mini",
            'llm.token_encoding': "cl100k_base"
        }.get(key, default)
        return config_loader
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for testing"""
        return {
            "ai_client": Mock(),
            "memory_repository": Mock(),
            "telemetry_adapter": Mock()
        }
    
    @pytest.fixture
    def service(self, mock_dependencies, mock_config_loader):
        """Create ConversationService instance for testing"""
        config = ConversationConfig(mock_config_loader)
        conversation = Conversation.create_new_conversation(user_id="test_user", config=config)
        return ConversationService(
            config=config,
            conversation=conversation,
            **mock_dependencies
        )
    
    def test_init(self, mock_dependencies, mock_config_loader):
        """Test initialization"""
        config = ConversationConfig(mock_config_loader)
        service = ConversationService(config=config, **mock_dependencies)
        assert service.conversation is not None
        assert service.ai_client == mock_dependencies["ai_client"]
        assert service.memory_repository == mock_dependencies["memory_repository"]
        assert service.telemetry_adapter == mock_dependencies["telemetry_adapter"]
    
    def test_service_attributes(self, service):
        """Test service attributes"""
        # Verify attributes are set correctly
        assert service.conversation is not None
        assert service.consecutive_ai_failures == 0
        assert service.clause_break_threshold == 30
    
    def test_handle_user_input_success(self, service, mock_dependencies):
        """Test successful handle_user_input"""
        user_text = "Hello"
        ai_response = "Hello! It's nice weather today."
        
        # Setup mocks
        service.generate_response = Mock(return_value=ai_response)
        
        # Execute
        result = service.handle_user_input(user_text)
        
        # Verify
        assert result == ai_response  # Verify handle_user_input returns AI response
        service.generate_response.assert_called_once_with(user_text)
        # Verify telemetry sending
        assert mock_dependencies["telemetry_adapter"].send_conversation.call_count == 2
        # Verify user utterance sending
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call("user", user_text)
        # Verify AI response sending
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call("assistant", ai_response)
        # Audio output is done by caller (VoiceInteractionService)
    
    def test_handle_user_input_no_response(self, service, mock_dependencies):
        """Test handle_user_input when no AI response"""
        user_text = "Hello"
        fallback_message = "Sorry, could you say that again?"
        
        # Setup mocks
        service.generate_response = Mock(return_value=None)
        
        # Execute
        result = service.handle_user_input(user_text)
        
        # Verify - fallback message is returned
        assert result == fallback_message
        service.generate_response.assert_called_once_with(user_text)
        # Verify telemetry sending (user and fallback message - 2 times)
        assert mock_dependencies["telemetry_adapter"].send_conversation.call_count == 2
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call("user", user_text)
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call("assistant", fallback_message)
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, service, mock_dependencies):
        """Test successful generate_response"""
        user_text = "What's the weather today?"
        ai_response = "Today's forecast is sunny."
        system_prompt = "You are a companion for Mr. Tanaka (78 years old). Recently his granddaughter Hanako visited."
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value=system_prompt)
        mock_dependencies["ai_client"].complete_chat = AsyncMock(return_value=ai_response)
        
        # Execute
        result = await service.generate_response(user_text)
        
        # Verify
        assert result == ai_response
        assert len(service.conversation.message_manager.messages) == 2  # User and AI messages
        assert service.conversation.message_manager.messages[0].content == user_text
        assert service.conversation.message_manager.messages[1].content == ai_response
        
        # Verify prompt_builder was called
        service.prompt_builder.build_system_prompt.assert_called_once()
        
        # Verify AI client was called correctly
        mock_dependencies["ai_client"].complete_chat.assert_called_once()
        call_args = mock_dependencies["ai_client"].complete_chat.call_args
        messages = call_args[0][0]  # messages list
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == user_text
    
    @pytest.mark.asyncio
    async def test_generate_response_failure(self, service, mock_dependencies):
        """Test when AI generation fails in generate_response"""
        user_text = "Hello"
        system_prompt = "You are a companion for elderly people."
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value=system_prompt)
        mock_dependencies["ai_client"].complete_chat = AsyncMock(return_value=None)
        
        # Execute
        result = await service.generate_response(user_text)
        
        # Verify
        assert result is None
        assert len(service.conversation.message_manager.messages) == 1  # User message only
    
    def test_handle_exit_command_flow(self, service, mock_dependencies):
        """Test handle_exit_command flow"""
        user_text = "Goodbye"
        
        # Execute
        result = service.handle_exit_command(user_text)
        
        # Verify
        assert result == service.conversation.config.farewell_message
        assert service.conversation.state.status == ConversationStatus.SLEEPING
        # Verify telemetry sending
        assert mock_dependencies["telemetry_adapter"].send_conversation.call_count == 2
        # Verify user utterance and AI response sending
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call(MessageRole.USER.value, user_text)
        mock_dependencies["telemetry_adapter"].send_conversation.assert_any_call(MessageRole.ASSISTANT.value, service.conversation.config.farewell_message)
    
    def test_is_exit_command_false(self, service):
        """Test is_exit_command with normal text"""
        user_text = "It's nice weather today"
        
        # Execute
        result = service.is_exit_command(user_text)
        
        # Verify
        assert result is False
    
    def test_conversation_sleeping_state(self, service):
        """Test conversation sleep state"""
        # Initial state
        assert service.conversation.state.status != ConversationStatus.SLEEPING
        
        # Enter sleep mode
        service.conversation.enter_sleep()
        assert service.conversation.state.status == ConversationStatus.SLEEPING
    
    def test_conversation_wake_from_sleep(self, service):
        """Test waking from conversation sleep"""
        # Enter sleep mode
        service.conversation.enter_sleep()
        assert service.conversation.state.status == ConversationStatus.SLEEPING
        
        # Exit sleep mode
        service.conversation.exit_sleep()
        assert service.conversation.state.status != ConversationStatus.SLEEPING
    
    def test_record_and_send_utterance(self, service, mock_dependencies):
        """Test _record_and_send_utterance"""
        # Send user utterance
        service._record_and_send_utterance("user", "Hello")
        
        # Verify telemetry sending
        mock_dependencies["telemetry_adapter"].send_conversation.assert_called_once_with("user", "Hello")
        
        # Send AI utterance
        mock_dependencies["telemetry_adapter"].reset_mock()
        service._record_and_send_utterance("ai", "Hello!")
        
        mock_dependencies["telemetry_adapter"].send_conversation.assert_called_once_with("ai", "Hello!")
    
    def test_system_prompt_builder(self, service, mock_dependencies):
        """Test SystemPromptBuilder"""
        expected_prompt = "You are a companion for Mr. Tanaka (78 years old).\nRecently his granddaughter Hanako visited."
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value=expected_prompt)
        
        # Execute
        result = service.prompt_builder.build_system_prompt()
        
        # Verify
        assert result == expected_prompt
        service.prompt_builder.build_system_prompt.assert_called_once()
    
    def test_system_prompt_without_memory(self, service):
        """Test prompt when memory_repository is not available"""
        # Recreate prompt_builder without memory repository
        from application.system_prompt_builder import SystemPromptBuilder
        service.prompt_builder = SystemPromptBuilder(None, service.conversation.config.config_loader)
        
        # Execute
        result = service.prompt_builder.build_system_prompt()
        
        # Verify - prompt is generated
        assert result is not None
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_generate_response_async(self, service, mock_dependencies):
        """Test async generate_response"""
        user_text = "What's the weather today?"
        ai_response = "Today's forecast is sunny."
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value="System prompt")
        mock_dependencies["ai_client"].complete_chat = AsyncMock(return_value=ai_response)
        
        # Execute
        result = await service.generate_response(user_text)
        
        # Verify
        assert result == ai_response
        mock_dependencies["ai_client"].complete_chat.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_response_timeout(self, service, mock_dependencies):
        """Test async generate_response timeout"""
        user_text = "Test"
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value="System prompt")
        async def slow_response(messages, system_prompt):
            await asyncio.sleep(61)  # Exceed 60 second timeout
            return "Response"
        
        mock_dependencies["ai_client"].complete_chat = slow_response
        
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            result = await service.generate_response(user_text)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_generate_response_stream(self, service, mock_dependencies):
        """Test streaming response generation"""
        user_text = "Hello"
        
        # Setup mocks
        service.prompt_builder.build_system_prompt = Mock(return_value="System prompt")
        
        # Simulate streaming events
        async def mock_stream():
            yield {"type": "delta", "text": "Hello, "}
            yield {"type": "delta", "text": "today is "}
            yield {"type": "delta", "text": "nice weather."}
            yield {"type": "final", "text": "Hello, today is nice weather."}
        
        mock_dependencies["ai_client"].stream_chat_completion = Mock(return_value=mock_stream())
        
        # Execute
        events = []
        async for event in service.generate_response_stream(user_text):
            events.append(event)
        
        # Verify
        assert len(events) >= 2  # At least segment and final
        assert events[-1]["type"] == "final"
        assert events[-1]["text"] == "Hello, today is nice weather."
    
    @pytest.mark.asyncio
    async def test_generate_response_stream_with_clause_break(self, service, mock_dependencies):
        """Test streaming with clause breaks"""
        user_text = "Test"
        
        service.prompt_builder.build_system_prompt = Mock(return_value="Prompt")
        service.clause_break_threshold = 30  # Clause break threshold
        
        # Simulate long sentence
        async def mock_stream():
            yield {"type": "delta", "text": "a" * 40 + ", "}  # 40 chars + punctuation
            yield {"type": "delta", "text": "b" * 20 + "."}  # 20 chars + period
            yield {"type": "final", "text": "a" * 40 + ", " + "b" * 20 + "."}
        
        mock_dependencies["ai_client"].stream_chat_completion = Mock(return_value=mock_stream())
        
        # Execute
        segments = []
        async for event in service.generate_response_stream(user_text):
            if event["type"] == "segment":
                segments.append(event["text"])
        
        # Verify - 2 segments created
        assert len(segments) == 2
    
    def test_is_exit_command(self, service):
        """Test exit command detection"""
        assert service.is_exit_command("goodbye") is True
        assert service.is_exit_command("bye") is True
        assert service.is_exit_command("good night") is True
        assert service.is_exit_command("see you") is True
        assert service.is_exit_command("hello") is False
    
    def test_handle_exit_command(self, service, mock_dependencies):
        """Test exit command handling"""
        user_text = "Goodbye"
        
        result = service.handle_exit_command(user_text)
        
        assert result == service.conversation.config.farewell_message
        assert service.conversation.is_sleeping() is True
        assert mock_dependencies["telemetry_adapter"].send_conversation.call_count == 2
    
    def test_consecutive_ai_failures(self, service, mock_dependencies):
        """Test handling of consecutive AI failures"""
        user_text = "Hello"
        
        # Mock generate_response to fail
        service.generate_response = Mock(return_value=None)
        
        # First failure
        result1 = service.handle_user_input(user_text)
        assert "again" in result1 or "Sorry" in result1
        assert service.consecutive_ai_failures == 1
        
        # Second failure
        result2 = service.handle_user_input(user_text)
        assert "again" in result2 or "Sorry" in result2
        assert service.consecutive_ai_failures == 2
        
        # Third failure - system error message
        result3 = service.handle_user_input(user_text)
        assert "system" in result3.lower() or "apologize" in result3.lower()
        assert service.consecutive_ai_failures == 3
        
        # Reset on success
        service.generate_response = Mock(return_value="Hello!")
        result4 = service.handle_user_input(user_text)
        assert result4 == "Hello!"
        assert service.consecutive_ai_failures == 0
    
    def test_recover_conversations(self, service):
        """Test conversation recovery"""
        recovery_data = {
            "messages": [
                {"speaker": "user", "text": "Hello"},
                {"speaker": "assistant", "text": "Hello!"}
            ],
            "timestamp": "2025-08-27T10:00:00",
            "count": 2
        }
        
        # Mock recovery_service properties
        service.recovery_service._recovery_success = True
        service.recovery_service._recovered_message_count = 2
        service.recovery_service._recovery_error = None
        
        with patch.object(service.recovery_service, 'recover_conversations'):
            result = service.recover_conversations(recovery_data)
        
        assert result["success"] is True
        assert result["message_count"] == 2
    
    def test_end_session(self, service, mock_dependencies):
        """Test session ending"""
        service.end_session()
        
        assert service.conversation.state.status.value == "ended"
        mock_dependencies["telemetry_adapter"].send_conversation.assert_called_once_with(
            "system", "Conversation session ended"
        )