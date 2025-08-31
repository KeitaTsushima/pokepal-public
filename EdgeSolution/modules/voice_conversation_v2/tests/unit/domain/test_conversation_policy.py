"""
Unit tests for ConversationPolicy domain model
"""
import pytest
from datetime import datetime, timedelta
from domain.conversation_policy import ConversationPolicy


class TestConversationPolicy:
    """Test class for ConversationPolicy"""
    
    @pytest.fixture
    def policy(self):
        """Test policy fixture"""
        return ConversationPolicy(
            max_conversation_length=300,  # 5 minutes
            max_silence_duration=30,      # 30 seconds
            max_tokens_per_message=500,
            farewell_keywords=["goodbye", "bye", "see you"]
        )
    
    def test_conversation_length_limit(self, policy):
        """Test conversation length limit"""
        start_time = datetime.now()
        
        # Within limit
        current_time = start_time + timedelta(seconds=200)
        assert policy.is_within_time_limit(start_time, current_time) is True
        
        # Exceeds limit
        current_time = start_time + timedelta(seconds=400)
        assert policy.is_within_time_limit(start_time, current_time) is False
    
    def test_silence_detection(self, policy):
        """Test silence detection"""
        last_activity = datetime.now()
        
        # Within silence threshold
        current_time = last_activity + timedelta(seconds=20)
        assert policy.is_silence_exceeded(last_activity, current_time) is False
        
        # Exceeds silence threshold
        current_time = last_activity + timedelta(seconds=40)
        assert policy.is_silence_exceeded(last_activity, current_time) is True
    
    def test_farewell_detection(self, policy):
        """Test farewell keyword detection"""
        # Farewell keywords
        assert policy.is_farewell("goodbye") is True
        assert policy.is_farewell("bye!") is True
        assert policy.is_farewell("see you tomorrow") is True
        
        # Non-farewell
        assert policy.is_farewell("hello") is False
        assert policy.is_farewell("thank you") is False
    
    def test_token_limit_validation(self, policy):
        """Test token limit validation"""
        # Within limit
        short_message = "This is a short message"
        assert policy.is_within_token_limit(short_message) is True
        
        # Exceeds limit (simulate long message)
        long_message = "This is a very long message. " * 100
        assert policy.is_within_token_limit(long_message) is False
    
    def test_conversation_continuation_decision(self, policy):
        """Test conversation continuation decision"""
        context = {
            'start_time': datetime.now() - timedelta(seconds=100),
            'last_activity': datetime.now() - timedelta(seconds=5),
            'message_count': 10,
            'current_message': "let's continue"
        }
        
        # Should continue
        assert policy.should_continue_conversation(context) is True
        
        # Should end due to farewell
        context['current_message'] = "goodbye"
        assert policy.should_continue_conversation(context) is False
    
    def test_response_timeout_policy(self, policy):
        """Test response timeout policy"""
        policy.response_timeout = 10  # 10 seconds
        
        request_time = datetime.now()
        
        # Within timeout
        response_time = request_time + timedelta(seconds=5)
        assert policy.is_response_timeout(request_time, response_time) is False
        
        # Timeout exceeded
        response_time = request_time + timedelta(seconds=15)
        assert policy.is_response_timeout(request_time, response_time) is True
    
    def test_retry_policy(self, policy):
        """Test retry policy"""
        policy.max_retries = 3
        policy.retry_delay = 1  # 1 second
        
        # Within retry limit
        assert policy.should_retry(attempt=1) is True
        assert policy.should_retry(attempt=2) is True
        assert policy.should_retry(attempt=3) is True
        
        # Exceeds retry limit
        assert policy.should_retry(attempt=4) is False
        
        # Get retry delay
        assert policy.get_retry_delay(attempt=1) == 1
        assert policy.get_retry_delay(attempt=2) == 2  # Exponential backoff
        assert policy.get_retry_delay(attempt=3) == 4
    
    def test_conversation_quality_rules(self, policy):
        """Test conversation quality rules"""
        policy.min_response_length = 10
        policy.max_response_length = 500
        
        # Too short
        assert policy.is_valid_response("short") is False
        
        # Valid length
        assert policy.is_valid_response("This is a response with appropriate length") is True
        
        # Too long
        long_response = "Long response " * 200
        assert policy.is_valid_response(long_response) is False
    
    def test_user_input_validation(self, policy):
        """Test user input validation"""
        # Valid inputs
        assert policy.is_valid_input("hello") is True
        assert policy.is_valid_input("I have a question") is True
        
        # Invalid inputs
        assert policy.is_valid_input("") is False
        assert policy.is_valid_input(None) is False
        assert policy.is_valid_input("   ") is False  # Only whitespace
    
    def test_conversation_state_rules(self, policy):
        """Test conversation state rules"""
        # Valid state transitions
        assert policy.is_valid_transition("idle", "listening") is True
        assert policy.is_valid_transition("listening", "processing") is True
        assert policy.is_valid_transition("processing", "speaking") is True
        assert policy.is_valid_transition("speaking", "idle") is True
        
        # Invalid transitions
        assert policy.is_valid_transition("idle", "speaking") is False
        assert policy.is_valid_transition("speaking", "listening") is False
    
    def test_memory_retention_policy(self, policy):
        """Test memory retention policy"""
        policy.memory_retention_days = 30
        
        # Recent memory - should retain
        recent_date = datetime.now() - timedelta(days=10)
        assert policy.should_retain_memory(recent_date) is True
        
        # Old memory - should not retain
        old_date = datetime.now() - timedelta(days=40)
        assert policy.should_retain_memory(old_date) is False
    
    def test_proactive_trigger_rules(self, policy):
        """Test proactive trigger rules"""
        policy.proactive_triggers = {
            'morning': {'hour': 8, 'message': 'Good morning'},
            'evening': {'hour': 20, 'message': 'Good evening'}
        }
        
        # Morning trigger
        morning_time = datetime.now().replace(hour=8, minute=0)
        trigger = policy.get_proactive_trigger(morning_time)
        assert trigger is not None
        assert trigger['message'] == 'Good morning'
        
        # No trigger
        noon_time = datetime.now().replace(hour=12, minute=0)
        trigger = policy.get_proactive_trigger(noon_time)
        assert trigger is None