#!/usr/bin/env python3
"""
Conversation Domain Model
Defines core conversation concepts and business rules
"""
from dataclasses import dataclass
from typing import List, Dict, Any
import uuid

from .message import ConversationStatus, MessageRole, ConversationError, MessageManager
from .token_manager import TokenManager
from .conversation_state import ConversationState
from .conversation_policy import ConversationPolicy


@dataclass
class ConversationConfig:
    """Configuration for conversation behavior and limits"""
    max_tokens: int
    default_system_prompt: str
    farewell_message: str
    llm_model_name: str
    tokenizer_encoding_method: str


class Conversation:
    """
    Conversation Entity
    
    Domain object that manages user-AI dialogue sessions.
    Provides comprehensive conversation operations including message
    addition/retrieval, state management, and termination detection.
    """
    
    def __init__(self, conversation_id: str, user_id: str, config: ConversationConfig):
        self.id = conversation_id
        self.user_id = user_id
        self.config = config
        
        # Initialize components
        self.token_manager = TokenManager(config.max_tokens, config.llm_model_name, config.tokenizer_encoding_method)
        self.message_manager = MessageManager(self.token_manager)
        self.state = ConversationState(conversation_id)
        self.policy = ConversationPolicy()
    
    @classmethod
    def create_new_conversation(cls, user_id: str, config: ConversationConfig) -> 'Conversation':
        if config is None:
            raise ValueError("ConversationConfig is required")
        conversation_id = str(uuid.uuid4())
        return cls(conversation_id, user_id, config)
    
    def _add_message(self, content: str, role: MessageRole) -> None:
        if self.state.status == ConversationStatus.ENDED:
            raise ConversationError("Cannot add messages to an ended conversation")
        
        if role == MessageRole.USER and self.state.status == ConversationStatus.SLEEPING:
            self.state.exit_sleep()
        
        if role == MessageRole.USER:
            self.message_manager.add_user_message(content)
        else:
            self.message_manager.add_assistant_message(content)
        
        self.state.update_last_activity()
    
    def add_user_message(self, content: str) -> None:
        self._add_message(content, MessageRole.USER)
    
    def add_assistant_message(self, content: str) -> None:
        self._add_message(content, MessageRole.ASSISTANT)
    
    def get_context_messages(self) -> List[Dict[str, str]]:
        return self.message_manager.get_context_messages()
    
    def is_exit_command(self, text: str) -> bool:
        return self.policy.is_exit_command(text)
    
    def enter_sleep(self) -> None:
        self.state.enter_sleep()
    
    def exit_sleep(self) -> None:
        self.state.exit_sleep()
    
    def is_sleeping(self) -> bool:
        return self.state.status == ConversationStatus.SLEEPING
    
    def get_current_messages(self) -> List[Any]:
        return list(self.message_manager.messages)
    
    def clear_messages(self) -> None:
        self.message_manager.messages.clear()
    
    def restore_messages(self, messages: List[Any]) -> None:
        self.message_manager.messages.extend(messages)
    
    def end_conversation(self) -> None:
        """End the conversation"""  
        self.state.end_conversation()
    
