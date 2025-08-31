"""
Unit tests for ConversationState domain model
"""
import pytest
from datetime import datetime
from domain.conversation_state import ConversationState, StateTransition


class TestConversationState:
    """Test class for ConversationState"""
    
    def test_initial_state(self):
        """Test initial state"""
        state = ConversationState()
        
        assert state.current_state == "idle"
        assert state.is_active is False
        assert state.start_time is None
    
    def test_state_transition_to_listening(self):
        """Test transition to listening state"""
        state = ConversationState()
        
        state.transition_to("listening")
        
        assert state.current_state == "listening"
        assert state.is_active is True
        assert state.start_time is not None
    
    def test_state_transition_to_processing(self):
        """Test transition to processing state"""
        state = ConversationState()
        state.transition_to("listening")
        
        state.transition_to("processing")
        
        assert state.current_state == "processing"
        assert state.is_active is True
    
    def test_state_transition_to_speaking(self):
        """Test transition to speaking state"""
        state = ConversationState()
        state.transition_to("processing")
        
        state.transition_to("speaking")
        
        assert state.current_state == "speaking"
        assert state.is_active is True
    
    def test_state_transition_to_idle(self):
        """Test transition to idle state"""
        state = ConversationState()
        state.transition_to("speaking")
        
        state.transition_to("idle")
        
        assert state.current_state == "idle"
        assert state.is_active is False
        assert state.end_time is not None
    
    def test_invalid_state_transition(self):
        """Test invalid state transition"""
        state = ConversationState()
        
        # idle -> speaking is invalid
        with pytest.raises(StateTransition):
            state.transition_to("speaking")
    
    def test_state_duration_tracking(self):
        """Test state duration tracking"""
        state = ConversationState()
        
        state.transition_to("listening")
        start = state.start_time
        
        import time
        time.sleep(0.1)
        
        duration = state.get_duration()
        assert duration >= 0.1
    
    def test_state_history(self):
        """Test state history"""
        state = ConversationState()
        
        transitions = ["listening", "processing", "speaking", "idle"]
        
        for next_state in transitions:
            state.transition_to(next_state)
        
        history = state.get_history()
        assert len(history) == 4
        assert [h['state'] for h in history] == transitions
    
    def test_concurrent_state_management(self):
        """Test concurrent state management"""
        state = ConversationState()
        
        # Manage multiple conversations
        state.start_conversation("conv1")
        assert state.active_conversations == ["conv1"]
        
        state.start_conversation("conv2")
        assert len(state.active_conversations) == 2
        
        state.end_conversation("conv1")
        assert state.active_conversations == ["conv2"]
    
    def test_state_persistence(self):
        """Test state persistence"""
        state = ConversationState()
        state.transition_to("listening")
        
        # Serialize
        data = state.to_dict()
        assert data['current_state'] == "listening"
        assert data['is_active'] is True
        
        # Deserialize
        new_state = ConversationState.from_dict(data)
        assert new_state.current_state == "listening"
        assert new_state.is_active is True
    
    def test_error_state_handling(self):
        """Test error state handling"""
        state = ConversationState()
        state.transition_to("listening")
        
        state.set_error("Connection failed")
        
        assert state.current_state == "error"
        assert state.error_message == "Connection failed"
        assert state.is_active is False
    
    def test_state_reset(self):
        """Test state reset"""
        state = ConversationState()
        state.transition_to("processing")
        state.set_error("Test error")
        
        state.reset()
        
        assert state.current_state == "idle"
        assert state.error_message is None
        assert state.is_active is False
        assert state.get_history() == []