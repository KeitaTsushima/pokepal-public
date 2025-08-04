#!/usr/bin/env python3
"""
Message-related class definitions
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Deque
from collections import deque
import logging


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationStatus(Enum):
    ACTIVE = "active"
    ENDED = "ended"
    SLEEPING = "sleeping"


class ConversationError(Exception):
    pass


@dataclass(frozen=True)
class Message:
    content: str
    role: MessageRole
    timestamp: datetime
    
    @classmethod
    def create_user_message(cls, content: str) -> 'Message':
        if not content:
            raise ValueError("Message content cannot be empty")
        return cls(
            content=content,
            role=MessageRole.USER,
            timestamp=datetime.now(timezone.utc)
        )
    
    @classmethod
    def create_assistant_message(cls, content: str) -> 'Message':
        if not content:
            raise ValueError("Message content cannot be empty")
        return cls(
            content=content,
            role=MessageRole.ASSISTANT,
            timestamp=datetime.now(timezone.utc)
        )


logger = logging.getLogger(__name__)


class MessageManager:
    """Manages message addition, retrieval, and operations"""
    
    def __init__(self, token_manager):
        """
        Args:
            token_manager: Token management instance
        """
        self.messages: Deque[Message] = deque()
        self.token_manager = token_manager
    
    def get_context_messages(self) -> List[Dict[str, str]]:
        """
        Returns:
            List of messages in role-content format
        """
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in self.messages
        ]
    
    def add_user_message(self, content: str) -> None:
        message = Message.create_user_message(content)
        self._add_message_to_list(message)
    
    def add_assistant_message(self, content: str) -> None:
        message = Message.create_assistant_message(content)
        self._add_message_to_list(message)
    
    def _add_message_to_list(self, message: "Message") -> None:
        """
        Add message to list with token management (internal use)
        
        Args:
            message: Message object to add
        """
        self.token_manager.add_message_tokens(message.content, message.role.value)        
        self.messages.append(message)
        self.token_manager.trim_messages(self.messages)
    
    def clear(self) -> None:
        """Clear messages (for resource cleanup)"""
        self.messages.clear()
        self.token_manager.clear()