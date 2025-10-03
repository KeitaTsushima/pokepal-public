"""
Conversation Service - Implements conversation-related use cases
"""
import asyncio
import logging
import re
import time
from typing import Optional, Dict, Any, List

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
                 telemetry_adapter = None,
                 clause_break_threshold: int = 30) -> None:
        """
        Args:
            config: Conversation configuration (required)
            conversation: Conversation domain object
            ai_client: AI processing client (Infrastructure layer)
            memory_repository: Memory management repository (Infrastructure layer)
            telemetry_adapter: Telemetry sending adapter (Adapters layer)
            clause_break_threshold: Threshold for clause-based streaming segmentation
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
        self.prompt_builder = SystemPromptBuilder(memory_repository, config.config_loader)
        
        # AI response failure counter
        self.consecutive_ai_failures = 0
        
        # Store streaming configuration value
        self.clause_break_threshold = int(clause_break_threshold)
        
        self.logger.info("ConversationService initialized")
    
    def handle_user_input(self, user_text: str) -> Optional[str]:
        self._record_and_send_utterance(MessageRole.USER.value, user_text)
        
        ai_response = self.generate_response(user_text)
        if not ai_response:
            self.consecutive_ai_failures += 1
            
            if self.consecutive_ai_failures >= 3:
                ai_response = self.conversation.config.config_loader.get(
                    'conversation.system_error_message', 
                    "申し訳ございません。システムに問題が発生しています。しばらくお待ちください。"
                )
                self.logger.error(f"AI response generation failed 3 times consecutively")
            else:
                ai_response = self.conversation.config.config_loader.get(
                    'conversation.fallback_message', 
                    "すみません、もう一度言っていただけますか？"
                )
                self.logger.warning(f"AI response generation failed ({self.consecutive_ai_failures}/3 times)")
        else:
            self.consecutive_ai_failures = 0
        
        self._record_and_send_utterance(MessageRole.ASSISTANT.value, ai_response)
        
        return ai_response
    
    async def generate_response(self, user_text: str) -> Optional[str]:
        messages = self._prepare_messages(user_text)
        
        if self.ai_client:
            system_prompt = self.prompt_builder.build_system_prompt()
            try:
                # Application-level timeout for LLM processing (60s as per expert recommendation)
                reply = await asyncio.wait_for(
                    self.ai_client.complete_chat(messages, system_prompt),
                    timeout=60.0
                )
                if reply:
                    self.conversation.add_assistant_message(reply)
                    return reply
            except asyncio.TimeoutError:
                self.logger.error("[perf] LLM response generation TIMEOUT after 60.000s - async architecture working correctly")
                return None
    
    async def generate_response_stream(self, user_text: str):
        t1 = time.monotonic()
        messages = self._prepare_messages(user_text)
        t2 = time.monotonic()
        self.logger.debug(f"[timing] _prepare_messages: {t2-t1:.3f}s")

        seg_buf: List[str] = []
        final_buf: List[str] = []
        seg_char_count = 0

        self.logger.info("LLM streaming start")
        t3 = time.monotonic()
        system_prompt = self.prompt_builder.build_system_prompt()
        t4 = time.monotonic()
        self.logger.debug(f"[timing] build_system_prompt: {t4-t3:.3f}s")
        
        try:
            # Create the stream generator
            t5 = time.monotonic()
            stream = self.ai_client.stream_chat_completion(messages, system_prompt)
            t6 = time.monotonic()
            self.logger.debug(f"[timing] stream_chat_completion call: {t6-t5:.3f}s")
            
            # Application-level timeout for entire streaming operation (60s as per expert recommendation)
            # Note: Direct iteration without timeout for now (Python 3.9 compatibility)
            t7 = time.monotonic()
            async for event in stream:
                if t7:  # First iteration
                    self.logger.debug(f"[timing] First stream event: {time.monotonic()-t7:.3f}s")
                    t7 = None
                if event.get("type") == "delta":
                    delta_text = event["text"]
                    seg_buf.append(delta_text)
                    final_buf.append(delta_text)
                    seg_char_count += len(delta_text)
                    
                    has_sentence_end = delta_text and len(delta_text) > 0 and delta_text[-1] in "。！？.!?"
                    has_clause_break = delta_text and len(delta_text) > 0 and delta_text[-1] in "、,;:"
                    
                    force_cut = seg_char_count >= 200  # Insurance for extremely long sentences without punctuation
                    should_cut = has_sentence_end or (has_clause_break and seg_char_count >= self.clause_break_threshold) or force_cut
                    
                    if should_cut:
                        seg = re.sub(r"\s+", " ", "".join(seg_buf)).strip()
                        self.logger.debug("LLM segment: %s...", seg[:40])
                        yield {"type": "segment", "text": seg}
                        seg_buf.clear()
                        seg_char_count = 0
                        
                elif event.get("type") == "final":
                    if seg_buf:
                        tail = re.sub(r"\s+", " ", "".join(seg_buf)).strip()
                        if tail:
                            yield {"type": "segment", "text": tail}
                        seg_buf.clear()

                    final_text = re.sub(r"\s+", " ", "".join(final_buf)).strip()
                    if final_text:
                        self.conversation.add_assistant_message(final_text)
                        self._record_and_send_utterance(MessageRole.ASSISTANT.value, final_text)
                    self.logger.info("LLM streaming end (chars=%d)", len(final_text))
                    yield {"type": "final", "text": final_text}
        except asyncio.TimeoutError:
            self.logger.error("[perf] LLM streaming TIMEOUT after 60.000s - async architecture working correctly")
            yield {"type": "error", "text": "LLM処理がタイムアウトしました"}
    
    def is_exit_command(self, user_text: str) -> bool:
        return self.conversation.is_exit_command(user_text)
    
    def handle_exit_command(self, user_text: str) -> str:
        self._record_and_send_utterance(MessageRole.USER.value, user_text)
        
        farewell_response = self.conversation.config.farewell_message
        self._record_and_send_utterance(MessageRole.ASSISTANT.value, farewell_response)
        
        self.conversation.enter_sleep()
        
        return farewell_response
    
    def _prepare_messages(self, user_text: str) -> List[Dict[str, str]]:
        """Prepare conversation context messages (without system prompt)"""
        self.conversation.add_user_message(user_text)
        return self.conversation.get_context_messages()
    
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
    
