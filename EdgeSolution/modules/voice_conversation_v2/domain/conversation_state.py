#!/usr/bin/env python3
"""
ConversationState - Conversation state management
"""
from datetime import datetime, timezone
from typing import Optional
import logging

from .message import ConversationStatus

logger = logging.getLogger(__name__)


class ConversationState:
    """Manages conversation state and lifecycle"""
    
    def __init__(self, conversation_id: str):
        """
        Args:
            conversation_id: Unique conversation identifier
        """
        self.conversation_id = conversation_id
        self.status = ConversationStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None
        self.sleep_entered_at: Optional[datetime] = None
    
    def enter_sleep(self) -> None:
        self.status = ConversationStatus.SLEEPING
        self.sleep_entered_at = datetime.now(timezone.utc)
        logger.info(f"Conversation {self.conversation_id} entered sleep mode")
    
    def exit_sleep(self) -> None:
        if self.sleep_entered_at:
            sleep_duration = datetime.now(timezone.utc) - self.sleep_entered_at
            logger.info(f"Conversation {self.conversation_id} exited sleep mode (sleep duration: {sleep_duration})")
        self.status = ConversationStatus.ACTIVE
        self.sleep_entered_at = None
        self.update_last_activity()
    
    def end_conversation(self) -> None:
        # TODO: Add resource cleanup for memory efficiency during long IoT operations
        # Currently: Status change only (working normally, implementation planned for scaling)
        self.status = ConversationStatus.ENDED
        self.ended_at = datetime.now(timezone.utc)
    
    def update_last_activity(self) -> None:
        """Update the timestamp of the last activity"""
        self.last_activity = datetime.now(timezone.utc)
    
