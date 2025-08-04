"""
Conversation Service - Implements conversation-related use cases
"""
import logging
from typing import Optional, Dict, Any

from domain.conversation import Conversation, ConversationConfig, MessageRole
from .conversation_recovery import ConversationRecovery
from .system_prompt_builder import SystemPromptBuilder


class ConversationService:
    """Use case implementation for conversation management"""
    
    def __init__(self,
                 config: ConversationConfig,
                 conversation: Optional[Conversation] = None,
                 ai_client = None,
                 memory_repository = None,
                 telemetry_adapter = None) -> None:
        """
        Args:
            config: Conversation configuration (required)
            conversation: Conversation domain object
            ai_client: AI processing client (Infrastructure layer)
            memory_repository: Memory management repository (Infrastructure layer)
            telemetry_adapter: Telemetry sending adapter (Adapters layer)
        """
        self.logger = logging.getLogger(__name__)
        
        # Domain object
        self.conversation = conversation or Conversation.create_new_conversation(
            user_id="default",  # TODO: Set actual user ID
            # TODO: Device sharing support - determine user_id via voice recognition/IC card/manual selection after user_id identification feature implementation
            config=config
        )
        
        # Dependency components (injected later)
        self.ai_client = ai_client
        self.memory_repository = memory_repository
        self.telemetry_adapter = telemetry_adapter
        
        # Recovery and prompt building services
        self.recovery_service = ConversationRecovery(self.conversation)
        self.prompt_builder = SystemPromptBuilder(memory_repository)
        
        # AI response failure counter
        self.consecutive_ai_failures = 0
        
        self.logger.info("ConversationService initialized")
    
    def handle_user_input(self, user_text: str) -> Optional[str]:
        self._record_and_send_utterance(MessageRole.USER.value, user_text)
        
        ai_response = self.generate_response(user_text)
        if not ai_response:
            self.consecutive_ai_failures += 1
            
            if self.consecutive_ai_failures >= 3:
                ai_response = self.conversation.config.get(
                    'system_error_message', 
                    "申し訳ございません。システムに問題が発生しています。しばらくお待ちください。"
                )
                self.logger.error(f"AI response generation failed 3 times consecutively")
            else:
                ai_response = self.conversation.config.get(
                    'fallback_message', 
                    "すみません、もう一度言っていただけますか？"
                )
                self.logger.warning(f"AI response generation failed ({self.consecutive_ai_failures}/3 times)")
        else:
            self.consecutive_ai_failures = 0
        
        self._record_and_send_utterance(MessageRole.ASSISTANT.value, ai_response)
        
        return ai_response
    
    def generate_response(self, user_text: str) -> Optional[str]:
        self.conversation.add_user_message(user_text)
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation.get_context_messages()
        ]
        
        if self.ai_client:
            memory_context = ""
            if self.memory_repository:
                memory_context = self.memory_repository.get_memory_context()
                self.logger.info(f"Memory context from repository: {memory_context[:200] if memory_context else 'Empty'}...")
            
            reply = self.ai_client.generate_response(messages, memory_context)
            if reply:
                self.conversation.add_assistant_message(reply)
                return reply
    
    def is_exit_command(self, user_text: str) -> bool:
        return self.conversation.is_exit_command(user_text)
    
    def handle_exit_command(self, user_text: str) -> str:
        self._record_and_send_utterance(MessageRole.USER.value, user_text)
        
        farewell_response = self.conversation.config.farewell_message
        self._record_and_send_utterance(MessageRole.ASSISTANT.value, farewell_response)
        
        self.conversation.enter_sleep()
        
        return farewell_response
    
    def _build_system_prompt(self) -> str:
        return self.prompt_builder.build_system_prompt(self.conversation.config)
    
    def _record_and_send_utterance(self, speaker: str, text: str) -> None:
        # Send telemetry (complete recording to CosmosDB)
        if self.telemetry_adapter:
            self.telemetry_adapter.send_conversation(speaker, text)
    
    def recover_conversations(self, recovery_data: Dict[str, Any]) -> Dict[str, Any]:
        self.recovery_service.recover_conversations(recovery_data)
        
        return {
            "success": self.recovery_service.recovery_success or False,
            "message_count": self.recovery_service.recovered_message_count,
            "error": self.recovery_service.recovery_error
        }
    
    def end_session(self) -> None:
        self.logger.info("Ending conversation session")
        
        self.conversation.end_conversation()
        
        if self.telemetry_adapter:
            self.telemetry_adapter.send_conversation("system", "Conversation session ended")
    
