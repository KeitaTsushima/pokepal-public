import pytest
from datetime import datetime
from typing import List, Optional
import sys
from pathlib import Path

# Add the parent directory to the path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from domain.conversation import (
    Conversation, 
    ConversationConfig
)
from domain.message import (
    Message, 
    MessageRole, 
    ConversationStatus, 
    ConversationError
)


@pytest.fixture
def default_config():
    """Default conversation configuration"""
    from unittest.mock import Mock
    mock_config_loader = Mock()
    mock_config_loader.get.side_effect = lambda key, default=None: {
        'memory.immediate_tokens': 1000,
        'llm.system_prompt': "You are a helpful assistant.",
        'conversation.farewell_message': "Goodbye. Let's talk again soon.",
        'llm.model': "gpt-4",
        'llm.token_encoding': "cl100k_base"
    }.get(key, default)
    
    return ConversationConfig(config_loader=mock_config_loader)


class TestConversation:
    """Test class for Conversation domain model"""
    
    def test_create_new_conversation(self, default_config):
        """Test creating a new conversation"""
        # Given: Information needed for conversation
        user_id = "user123"
        
        # When: Create new conversation
        conversation = Conversation.create_new_conversation(user_id=user_id, config=default_config)
        
        # Then: Should be created correctly
        assert conversation.id is not None
        assert conversation.user_id == user_id
        assert conversation.state.started_at is not None
        assert conversation.state.status == ConversationStatus.ACTIVE
        assert len(conversation.message_manager.messages) == 0
    
    def test_add_user_message(self, default_config):
        """Test adding user messages (first and multiple)"""
        # Given: Active conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        
        # When: Add first user message
        first_message = "Tell me about Pikachu"
        conversation.add_user_message(first_message)
        
        # Then: First message should be added correctly
        assert len(conversation.message_manager.messages) == 1
        assert conversation.message_manager.messages[0].content == first_message
        assert conversation.message_manager.messages[0].role == MessageRole.USER
        assert conversation.message_manager.messages[0].timestamp is not None
        
        # When: Add second user message
        second_message = "What does it evolve into?"
        conversation.add_user_message(second_message)
        
        # Then: Second message should also be added correctly
        assert len(conversation.message_manager.messages) == 2
        assert conversation.message_manager.messages[1].content == second_message
        assert conversation.message_manager.messages[1].role == MessageRole.USER
        assert conversation.message_manager.messages[1].timestamp is not None
    
    def test_add_assistant_message(self, default_config):
        """Test adding assistant messages (first and multiple)"""
        # Given: Active conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        
        # When: Add first assistant message (like a reminder)
        first_message = "It's time for your medication. Have you taken it?"
        conversation.add_assistant_message(first_message)
        
        # Then: First message should be added correctly
        assert len(conversation.message_manager.messages) == 1
        assert conversation.message_manager.messages[0].content == first_message
        assert conversation.message_manager.messages[0].role == MessageRole.ASSISTANT
        assert conversation.message_manager.messages[0].timestamp is not None
        
        # When: Add second assistant message
        second_message = "How are you feeling?"
        conversation.add_assistant_message(second_message)
        
        # Then: Second message should also be added correctly
        assert len(conversation.message_manager.messages) == 2
        assert conversation.message_manager.messages[1].content == second_message
        assert conversation.message_manager.messages[1].role == MessageRole.ASSISTANT
        assert conversation.message_manager.messages[1].timestamp is not None
    
    def test_mixed_conversation_flow(self, default_config):
        """Test mixed conversation flow between user and assistant"""
        # Given: Active conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        
        # When: Add multiple messages alternately
        conversation.add_user_message("Tell me about Pikachu")
        conversation.add_assistant_message("Pikachu is an Electric-type Pokémon")
        conversation.add_user_message("What does it evolve into?")
        conversation.add_assistant_message("It evolves into Raichu")
        
        # Then: All messages should be recorded in correct order
        assert len(conversation.message_manager.messages) == 4
        assert conversation.message_manager.messages[0].role == MessageRole.USER
        assert conversation.message_manager.messages[1].role == MessageRole.ASSISTANT
        assert conversation.message_manager.messages[2].role == MessageRole.USER
        assert conversation.message_manager.messages[3].role == MessageRole.ASSISTANT
    
    def test_end_conversation(self, default_config):
        """Test ending a conversation"""
        # Given: Active conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        conversation.add_user_message("Goodbye")
        
        # When: End conversation
        conversation.end_conversation()
        
        # Then: Status should be changed
        assert conversation.state.status == ConversationStatus.ENDED
        assert conversation.state.ended_at is not None
    
    def test_cannot_add_message_to_ended_conversation(self, default_config):
        """Test that messages cannot be added to ended conversation"""
        # Given: Ended conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        conversation.add_user_message("test")
        conversation.end_conversation()
        
        # When/Then: Trying to add message should raise exception
        with pytest.raises(ConversationError):
            conversation.add_user_message("New message")


class TestMessage:
    """Test class for Message value object"""
    
    def test_create_user_message(self):
        """Test creating user message"""
        # When: Create user message
        message = Message.create_user_message("Hello")
        
        # Then: Should be created correctly
        assert message.content == "Hello"
        assert message.role == MessageRole.USER
        assert message.timestamp is not None
    
    def test_create_assistant_message(self):
        """Test creating assistant message"""
        # When: Create assistant message
        message = Message.create_assistant_message("Hello!")
        
        # Then: Should be created correctly
        assert message.content == "Hello!"
        assert message.role == MessageRole.ASSISTANT
        assert message.timestamp is not None
    
    def test_empty_message_not_allowed(self):
        """Test that empty messages are not allowed"""
        # When/Then: Trying to create empty message should raise exception
        with pytest.raises(ValueError):
            Message.create_user_message("")


class TestSleepMode:
    """Test class for sleep mode functionality"""
    
    def test_enter_and_exit_sleep(self, default_config):
        """Test entering and exiting sleep mode"""
        # Given: Active conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        
        # When: Enter sleep mode
        conversation.enter_sleep()
        
        # Then: Status should be changed
        assert conversation.state.status == ConversationStatus.SLEEPING
        assert conversation.state.sleep_entered_at is not None
        
        # When: Exit sleep mode
        conversation.exit_sleep()
        
        # Then: Status should be restored
        assert conversation.state.status == ConversationStatus.ACTIVE
        assert conversation.state.sleep_entered_at is None
    
    def test_user_message_exits_sleep(self, default_config):
        """Test that user message exits sleep mode"""
        # Given: Sleeping conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        conversation.enter_sleep()
        assert conversation.state.status == ConversationStatus.SLEEPING
        
        # When: User sends message
        conversation.add_user_message("Good morning")
        
        # Then: Should automatically return to active
        assert conversation.state.status == ConversationStatus.ACTIVE
        assert conversation.state.sleep_entered_at is None
        assert len(conversation.message_manager.messages) == 1
    
    def test_assistant_message_keeps_sleep(self, default_config):
        """Test that assistant message does not exit sleep mode"""
        # Given: Sleeping conversation
        conversation = Conversation.create_new_conversation(user_id="user123", config=default_config)
        conversation.enter_sleep()
        assert conversation.state.status == ConversationStatus.SLEEPING
        
        # When: Assistant sends message (like reminder)
        conversation.add_assistant_message("Time for your medication")
        
        # Then: Sleep state should be maintained
        assert conversation.state.status == ConversationStatus.SLEEPING
        assert conversation.state.sleep_entered_at is not None
        assert len(conversation.message_manager.messages) == 1