"""
Unit tests for TokenManager domain model
"""
import pytest
from domain.token_manager import TokenManager
from domain.message import Message, MessageRole
from datetime import datetime


class TestTokenManager:
    """Test class for TokenManager"""
    
    @pytest.fixture
    def token_manager(self):
        """TokenManager instance"""
        return TokenManager(max_tokens=1000)
    
    def test_init(self, token_manager):
        """Test initialization"""
        assert token_manager.max_tokens == 1000
        assert token_manager.current_tokens == 0
        assert len(token_manager.messages) == 0
    
    def test_estimate_tokens(self, token_manager):
        """Test token count estimation"""
        # Japanese text (approximately 1 token per 2 characters)
        japanese_text = "こんにちは、今日はいい天気ですね。"
        tokens = token_manager.estimate_tokens(japanese_text)
        assert tokens > 0
        assert tokens < len(japanese_text)  # Should be less than character count
        
        # English text (approximately 1 token per 4 characters)
        english_text = "Hello, how are you today?"
        tokens = token_manager.estimate_tokens(english_text)
        assert tokens > 0
        assert tokens < len(english_text)
    
    def test_add_message(self, token_manager):
        """Test adding a message"""
        message = Message(
            role=MessageRole.USER,
            content="Test message",
            timestamp=datetime.now()
        )
        
        token_manager.add_message(message)
        
        assert len(token_manager.messages) == 1
        assert token_manager.messages[0] == message
        assert token_manager.current_tokens > 0
    
    def test_add_multiple_messages(self, token_manager):
        """Test adding multiple messages"""
        messages = [
            Message(MessageRole.USER, "Question 1", datetime.now()),
            Message(MessageRole.ASSISTANT, "Answer 1", datetime.now()),
            Message(MessageRole.USER, "Question 2", datetime.now()),
            Message(MessageRole.ASSISTANT, "Answer 2", datetime.now())
        ]
        
        for msg in messages:
            token_manager.add_message(msg)
        
        assert len(token_manager.messages) == 4
        assert token_manager.current_tokens > 0
    
    def test_token_limit_enforcement(self, token_manager):
        """Test token limit enforcement"""
        token_manager.max_tokens = 50  # Set low limit
        
        # Add messages until limit is exceeded
        for i in range(20):
            message = Message(
                MessageRole.USER,
                f"This is a long message. Number: {i}",
                timestamp=datetime.now()
            )
            token_manager.add_message(message)
        
        # Check that old messages are removed
        assert token_manager.current_tokens <= token_manager.max_tokens
        assert len(token_manager.messages) < 20
    
    def test_clear_messages(self, token_manager):
        """Test clearing messages"""
        # Add some messages
        for i in range(5):
            token_manager.add_message(
                Message(MessageRole.USER, f"Message {i}", datetime.now())
            )
        
        assert len(token_manager.messages) > 0
        assert token_manager.current_tokens > 0
        
        # Clear messages
        token_manager.clear()
        
        assert len(token_manager.messages) == 0
        assert token_manager.current_tokens == 0
    
    def test_get_messages_as_list(self, token_manager):
        """Test getting messages as list"""
        messages = [
            Message(MessageRole.USER, "User message", datetime.now()),
            Message(MessageRole.ASSISTANT, "Assistant message", datetime.now())
        ]
        
        for msg in messages:
            token_manager.add_message(msg)
        
        message_list = token_manager.get_messages_as_list()
        
        assert len(message_list) == 2
        assert all(isinstance(msg, dict) for msg in message_list)
        assert message_list[0]['role'] == 'user'
        assert message_list[0]['content'] == 'User message'
    
    def test_prune_old_messages(self, token_manager):
        """Test pruning old messages"""
        token_manager.max_tokens = 100
        
        # Add many messages
        for i in range(10):
            token_manager.add_message(
                Message(MessageRole.USER, f"Message number {i}" * 5, datetime.now())
            )
        
        # Verify pruning occurred
        assert token_manager.current_tokens <= token_manager.max_tokens
        
        # Most recent messages should be kept
        if len(token_manager.messages) > 0:
            last_message = token_manager.messages[-1]
            assert "Message number 9" in last_message.content or len(token_manager.messages) < 10
    
    def test_system_message_handling(self, token_manager):
        """Test system message handling"""
        system_message = Message(
            MessageRole.SYSTEM,
            "You are a helpful assistant",
            datetime.now()
        )
        
        token_manager.add_message(system_message)
        
        # Add more messages
        for i in range(5):
            token_manager.add_message(
                Message(MessageRole.USER, f"Message {i}", datetime.now())
            )
        
        # System message should be preserved if possible
        messages = token_manager.get_messages_as_list()
        has_system = any(msg['role'] == 'system' for msg in messages)
        assert has_system or token_manager.current_tokens > token_manager.max_tokens
    
    def test_token_calculation_accuracy(self, token_manager):
        """Test token calculation accuracy"""
        # Known text patterns
        test_cases = [
            ("Hello", 1, 3),  # Expected 1-3 tokens
            ("こんにちは", 2, 5),  # Expected 2-5 tokens  
            ("This is a longer sentence with multiple words.", 8, 12),  # Expected 8-12 tokens
            ("日本語の長い文章をテストしています。", 8, 15)  # Expected 8-15 tokens
        ]
        
        for text, min_tokens, max_tokens in test_cases:
            tokens = token_manager.estimate_tokens(text)
            assert min_tokens <= tokens <= max_tokens, f"Text: {text}, Got: {tokens}, Expected: {min_tokens}-{max_tokens}"
    
    def test_empty_message_handling(self, token_manager):
        """Test empty message handling"""
        empty_message = Message(MessageRole.USER, "", datetime.now())
        token_manager.add_message(empty_message)
        
        assert len(token_manager.messages) == 1
        assert token_manager.current_tokens >= 0  # Should handle empty content gracefully