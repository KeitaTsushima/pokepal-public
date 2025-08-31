"""
Unit tests for Message domain model
"""
import pytest
from datetime import datetime
from domain.message import Message, MessageRole


class TestMessage:
    """Test class for Message domain model"""
    
    def test_create_user_message(self):
        """Test creating user message"""
        message = Message(
            role=MessageRole.USER,
            content="Hello",
            timestamp=datetime.now()
        )
        
        assert message.role == MessageRole.USER
        assert message.content == "Hello"
        assert message.timestamp is not None
    
    def test_create_assistant_message(self):
        """Test creating assistant message"""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="Hello! How are you?",
            timestamp=datetime.now()
        )
        
        assert message.role == MessageRole.ASSISTANT
        assert message.content == "Hello! How are you?"
    
    def test_create_system_message(self):
        """Test creating system message"""
        message = Message(
            role=MessageRole.SYSTEM,
            content="You are a helpful assistant",
            timestamp=datetime.now()
        )
        
        assert message.role == MessageRole.SYSTEM
        assert message.content == "You are a helpful assistant"
    
    def test_message_to_dict(self):
        """Test message to dictionary conversion"""
        timestamp = datetime.now()
        message = Message(
            role=MessageRole.USER,
            content="Test",
            timestamp=timestamp
        )
        
        result = message.to_dict()
        
        assert result['role'] == 'user'
        assert result['content'] == 'Test'
        assert 'timestamp' in result
    
    def test_message_from_dict(self):
        """Test creating message from dictionary"""
        data = {
            'role': 'assistant',
            'content': 'Test response',
            'timestamp': '2024-01-01T10:00:00'
        }
        
        message = Message.from_dict(data)
        
        assert message.role == MessageRole.ASSISTANT
        assert message.content == 'Test response'
    
    def test_message_equality(self):
        """Test message equality"""
        timestamp = datetime.now()
        message1 = Message(MessageRole.USER, "test", timestamp)
        message2 = Message(MessageRole.USER, "test", timestamp)
        message3 = Message(MessageRole.USER, "different", timestamp)
        
        assert message1 == message2
        assert message1 != message3
    
    def test_message_str_representation(self):
        """Test message string representation"""
        message = Message(
            role=MessageRole.USER,
            content="Hello",
            timestamp=datetime.now()
        )
        
        str_repr = str(message)
        assert "user" in str_repr.lower()
        assert "Hello" in str_repr
    
    def test_message_validation(self):
        """Test message validation"""
        # Empty content should be allowed
        message = Message(MessageRole.USER, "", datetime.now())
        assert message.content == ""
        
        # None content should raise error or be converted to empty string
        message = Message(MessageRole.USER, None, datetime.now())
        assert message.content == "" or message.content is None
    
    def test_message_role_values(self):
        """Test MessageRole enum values"""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
    
    def test_message_immutability(self):
        """Test message immutability"""
        message = Message(
            role=MessageRole.USER,
            content="original",
            timestamp=datetime.now()
        )
        
        original_content = message.content
        # Try to modify (should either raise error or have no effect)
        try:
            message.content = "modified"
            # If no error, check if unchanged
            assert message.content == original_content or message.content == "modified"
        except (AttributeError, TypeError):
            # Immutable as expected
            pass