"""
Conversation Recovery - Startup conversation recovery service

This module handles conversation history recovery during startup.
Recovers conversations since the last memory summary generation,
enabling natural conversation continuity after restarts.
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from domain.message import MessageRole


@dataclass
class ConversationMessage:
    speaker: str
    text: str
    timestamp: Optional[str] = None


@dataclass 
class RestoreData:
    messages: List[Dict[str, Any]]
    timestamp: Optional[str]
    count: int
    
    def validate(self) -> bool:
        return (
            isinstance(self.messages, list) and
            isinstance(self.count, int) and
            self.count >= 0 and
            len(self.messages) == self.count
        )


class ConversationRecoveryError(Exception):
    pass


class ConversationRecovery:    
    def __init__(self, conversation):
        self._logger = logging.getLogger(__name__)
        self._conversation = conversation
        self._recovery_completed = False
        self._recovered_message_count = 0
        self._recovery_success = None  # None: Not executed, True: Success, False: Failure
        self._recovery_error = None    # Error information on failure
    
    def recover_conversations(self, recovery_data: Dict[str, Any]) -> None:
        """
        Recover conversation history since last memory summary generation
        
        Args:
            recovery_data: Recovery data
                - messages: List of conversation history
                - timestamp: Recovery data timestamp  
                - count: Number of messages
                
        Raises:
            ConversationRecoveryError: When recovery process encounters an error
            ValueError: When invalid data is provided
        """
        # One-time execution check
        if self._recovery_completed:
            self._logger.info("Conversation recovery already completed, skipping")
            return
        
        try:
            parsed_data = self._parse_recovery_data(recovery_data)
            if not parsed_data.validate():
                raise ValueError("Invalid recovery data structure")
            
            self._logger.info(
                f"Recovering {parsed_data.count} conversations from {parsed_data.timestamp}"
            )
            
            current_messages = self._conversation.get_current_messages()
            self._conversation.clear_messages()
            
            # Recover conversations since last memory summary and count successes
            recovered_count = self._recover_and_count_messages(parsed_data.messages)
            
            # Re-add current conversation
            self._conversation.restore_messages(current_messages)
            
            self._recovery_completed = True
            self._recovered_message_count = recovered_count
            self._recovery_success = True
            self._recovery_error = None
            self._logger.info(f"Successfully recovered {recovered_count} conversations")
            
        except Exception as e:
            error_type = "Data validation error" if isinstance(e, ValueError) else "Unexpected error"
            self._logger.error(f"{error_type} in recover_conversations: {e}")
            self._recovery_completed = True
            self._recovery_success = False
            self._recovery_error = str(e)
            # Don't raise exceptions as results are processed by ConversationService
    
    def _parse_recovery_data(self, recovery_data: Dict[str, Any]) -> RestoreData:
        return RestoreData(
            messages=recovery_data.get("messages", []),
            timestamp=recovery_data.get("timestamp"),
            count=recovery_data.get("count", 0)
        )
    
    def _recover_and_count_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Recover message list and return success count"""
        recovered_count = 0
        
        for msg in messages:
            try:
                parsed_msg = self._parse_message(msg)
                if parsed_msg:
                    self._add_message_to_repository(parsed_msg)
                    recovered_count += 1
                    self._logger.debug(
                        f"Recovered message: {parsed_msg.speaker}: {parsed_msg.text[:50]}..."
                    )
            except Exception as e:
                self._logger.error(f"Error recovering individual message: {e}")
                continue
        
        return recovered_count
    
    def _parse_message(self, msg: Dict[str, Any]) -> Optional[ConversationMessage]:
        speaker = msg.get("speaker")
        text = msg.get("text")
        timestamp = msg.get("timestamp")
        
        if not speaker or not text:
            return None
        
        if speaker not in [MessageRole.USER.value, MessageRole.ASSISTANT.value]:
            return None
        
        return ConversationMessage(
            speaker=speaker,
            text=text,
            timestamp=timestamp
        )
    
    def _add_message_to_repository(self, message: ConversationMessage) -> None:
        if message.speaker == MessageRole.USER.value:
            self._conversation.add_user_message(message.text)
        elif message.speaker == MessageRole.ASSISTANT.value:
            self._conversation.add_assistant_message(message.text)
        else:
            raise ValueError(f"Unknown speaker type: {message.speaker}")
    
    @property
    def is_recovery_completed(self) -> bool:
        return self._recovery_completed
    
    @property
    def recovered_message_count(self) -> int:
        return self._recovered_message_count
    
    @property
    def recovery_success(self) -> Optional[bool]:
        return self._recovery_success
    
    @property
    def recovery_error(self) -> Optional[str]:
        return self._recovery_error