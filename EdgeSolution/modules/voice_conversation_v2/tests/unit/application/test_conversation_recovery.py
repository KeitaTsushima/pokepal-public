"""
Unit tests for ConversationRecovery
Tests for conversation history recovery functionality
"""
import pytest
from unittest.mock import Mock, MagicMock
from application.conversation_recovery import (
    ConversationRecovery, ConversationMessage, RestoreData,
    ConversationRecoveryError
)
from domain.message import MessageRole


class TestConversationRecovery:
    """Test class for ConversationRecovery"""
    
    @pytest.fixture
    def mock_conversation(self):
        """Mock Conversation"""
        conversation = Mock()
        conversation.get_current_messages.return_value = []
        conversation.clear_messages = Mock()
        conversation.restore_messages = Mock()
        conversation.add_user_message = Mock()
        conversation.add_assistant_message = Mock()
        return conversation
    
    @pytest.fixture
    def recovery(self, mock_conversation):
        """Instance under test"""
        return ConversationRecovery(mock_conversation)
    
    @pytest.fixture
    def valid_recovery_data(self):
        """Valid recovery data"""
        return {
            "messages": [
                {
                    "speaker": "user",
                    "text": "こんにちは",
                    "timestamp": "2025-08-24T10:00:00"
                },
                {
                    "speaker": "assistant",
                    "text": "こんにちは！今日はいい天気ですね。",
                    "timestamp": "2025-08-24T10:00:05"
                }
            ],
            "timestamp": "2025-08-24T10:00:00",
            "count": 2
        }
    
    def test_init(self, recovery):
        """Test initialization"""
        assert recovery._recovery_completed is False
        assert recovery._recovered_message_count == 0
        assert recovery._recovery_success is None
        assert recovery._recovery_error is None
    
    def test_recover_conversations_success(self, recovery, mock_conversation, valid_recovery_data):
        """Test normal conversation recovery"""
        # Execute
        recovery.recover_conversations(valid_recovery_data)
        
        # Verify
        assert recovery._recovery_completed is True
        assert recovery._recovered_message_count == 2
        assert recovery._recovery_success is True
        assert recovery._recovery_error is None
        
        # Check method calls
        mock_conversation.get_current_messages.assert_called_once()
        mock_conversation.clear_messages.assert_called_once()
        mock_conversation.add_user_message.assert_called_once_with("こんにちは")
        mock_conversation.add_assistant_message.assert_called_once_with("こんにちは！今日はいい天気ですね。")
        mock_conversation.restore_messages.assert_called_once()
    
    def test_recover_conversations_already_completed(self, recovery, valid_recovery_data):
        """Test when recovery is already completed"""
        # First execution
        recovery.recover_conversations(valid_recovery_data)
        
        # Second execution
        recovery._conversation.clear_messages.reset_mock()
        recovery.recover_conversations(valid_recovery_data)
        
        # Nothing is executed on second run
        recovery._conversation.clear_messages.assert_not_called()
    
    def test_recover_conversations_invalid_data(self, recovery):
        """Test recovery with invalid data"""
        invalid_data = {
            "messages": "not_a_list",  # Not a list
            "timestamp": "2025-08-24T10:00:00",
            "count": 2
        }
        
        recovery.recover_conversations(invalid_data)
        
        assert recovery._recovery_completed is True
        assert recovery._recovery_success is False
        assert recovery._recovery_error is not None
        assert "Invalid recovery data structure" in recovery._recovery_error
    
    def test_recover_conversations_empty_data(self, recovery, mock_conversation):
        """Test recovery with empty data"""
        empty_data = {
            "messages": [],
            "timestamp": "2025-08-24T10:00:00",
            "count": 0
        }
        
        recovery.recover_conversations(empty_data)
        
        assert recovery._recovery_completed is True
        assert recovery._recovered_message_count == 0
        assert recovery._recovery_success is True
        assert recovery._recovery_error is None
    
    def test_recover_conversations_partial_failure(self, recovery, mock_conversation):
        """Test partial message recovery failure"""
        data_with_invalid = {
            "messages": [
                {
                    "speaker": "user",
                    "text": "有効なメッセージ",
                    "timestamp": "2025-08-24T10:00:00"
                },
                {
                    "speaker": "invalid_role",  # Invalid role
                    "text": "無効なメッセージ",
                    "timestamp": "2025-08-24T10:00:05"
                },
                {
                    "speaker": "assistant",
                    "text": "別の有効なメッセージ",
                    "timestamp": "2025-08-24T10:00:10"
                }
            ],
            "timestamp": "2025-08-24T10:00:00",
            "count": 3
        }
        
        recovery.recover_conversations(data_with_invalid)
        
        # Only 2 valid messages are recovered
        assert recovery._recovered_message_count == 2
        assert recovery._recovery_success is True
        mock_conversation.add_user_message.assert_called_once_with("有効なメッセージ")
        mock_conversation.add_assistant_message.assert_called_once_with("別の有効なメッセージ")
    
    def test_recover_conversations_missing_fields(self, recovery):
        """Test messages with missing required fields"""
        data_missing_fields = {
            "messages": [
                {
                    "speaker": "user",
                    # Missing text field
                    "timestamp": "2025-08-24T10:00:00"
                },
                {
                    # Missing speaker field
                    "text": "テキストのみ",
                    "timestamp": "2025-08-24T10:00:05"
                }
            ],
            "timestamp": "2025-08-24T10:00:00",
            "count": 2
        }
        
        recovery.recover_conversations(data_missing_fields)
        
        # Neither message is recovered
        assert recovery._recovered_message_count == 0
        assert recovery._recovery_success is True
    
    def test_properties(self, recovery, valid_recovery_data):
        """Test properties"""
        # Initial state
        assert recovery.is_recovery_completed is False
        assert recovery.recovered_message_count == 0
        assert recovery.recovery_success is None
        assert recovery.recovery_error is None
        
        # After recovery execution
        recovery.recover_conversations(valid_recovery_data)
        
        assert recovery.is_recovery_completed is True
        assert recovery.recovered_message_count == 2
        assert recovery.recovery_success is True
        assert recovery.recovery_error is None
    
    def test_restore_messages_with_current_conversation(self, recovery, mock_conversation, valid_recovery_data):
        """Test recovery while preserving current conversation"""
        current_messages = [
            {"role": "user", "content": "現在の会話"},
            {"role": "assistant", "content": "現在の応答"}
        ]
        mock_conversation.get_current_messages.return_value = current_messages
        
        recovery.recover_conversations(valid_recovery_data)
        
        # Current conversation is restored
        mock_conversation.restore_messages.assert_called_once_with(current_messages)


class TestRestoreData:
    """Test class for RestoreData"""
    
    def test_validate_valid_data(self):
        """Test validation of valid data"""
        data = RestoreData(
            messages=[{"speaker": "user", "text": "test"}],
            timestamp="2025-08-24T10:00:00",
            count=1
        )
        assert data.validate() is True
    
    def test_validate_invalid_messages_type(self):
        """When messages has invalid type"""
        data = RestoreData(
            messages="not_a_list",
            timestamp="2025-08-24T10:00:00",
            count=1
        )
        assert data.validate() is False
    
    def test_validate_invalid_count_type(self):
        """When count has invalid type"""
        data = RestoreData(
            messages=[],
            timestamp="2025-08-24T10:00:00",
            count="not_an_int"
        )
        assert data.validate() is False
    
    def test_validate_negative_count(self):
        """When count is negative"""
        data = RestoreData(
            messages=[],
            timestamp="2025-08-24T10:00:00",
            count=-1
        )
        assert data.validate() is False
    
    def test_validate_count_mismatch(self):
        """When count doesn't match message count"""
        data = RestoreData(
            messages=[{"speaker": "user", "text": "test"}],
            timestamp="2025-08-24T10:00:00",
            count=2  # Actually 1 message
        )
        assert data.validate() is False


class TestConversationMessage:
    """Test class for ConversationMessage"""
    
    def test_create_with_timestamp(self):
        """Create message with timestamp"""
        msg = ConversationMessage(
            speaker="user",
            text="テストメッセージ",
            timestamp="2025-08-24T10:00:00"
        )
        assert msg.speaker == "user"
        assert msg.text == "テストメッセージ"
        assert msg.timestamp == "2025-08-24T10:00:00"
    
    def test_create_without_timestamp(self):
        """Create message without timestamp"""
        msg = ConversationMessage(
            speaker="assistant",
            text="応答メッセージ"
        )
        assert msg.speaker == "assistant"
        assert msg.text == "応答メッセージ"
        assert msg.timestamp is None