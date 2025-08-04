#!/usr/bin/env python3
"""
TokenManager - Token counting and limit management
"""
from typing import Optional, Deque
from collections import deque
import tiktoken
import logging

logger = logging.getLogger(__name__)


class TokenManager:
    """Handles token counting and limit management"""
    
    def __init__(self, max_tokens: int, llm_model_name: str, tokenizer_encoding_method: str):
        self.max_tokens = max_tokens
        self.model_name = llm_model_name
        self.token_encoding = tokenizer_encoding_method
        self._encoding: Optional[tiktoken.Encoding] = None
        self._token_counts: Deque[int] = deque()
        self._total_tokens: int = 0
    
    def count_tokens(self, text: str) -> int:
        """
        Args:
            text: Text to calculate tokens for
            
        Returns:
            Number of tokens
        """
        if self._encoding is None:
            try:
                self._encoding = tiktoken.encoding_for_model(self.model_name)
            except KeyError:
                self._encoding = tiktoken.get_encoding(self.token_encoding)
        return len(self._encoding.encode(text))
    
    def add_message_tokens(self, content: str, role_name: str) -> int:
        """
        Args:
            content: Message content
            role_name: Role name ("user" or "assistant")
            
        Returns:
            Calculated token count
        """
        message_text = f"{role_name}: {content}"
        token_count = self.count_tokens(message_text)
        
        self._token_counts.append(token_count)
        self._total_tokens += token_count
        
        return token_count
    
    def trim_messages(self, messages: Deque) -> int:
        """
        Remove old messages to stay within token limits
        
        Args:
            messages: Message deque (will be modified)
            
        Returns:
            Number of deleted messages
        """
        initial_count = len(messages)
        
        # Delete old messages while token count exceeds limit
        # TODO: Protection mechanism needed for important information (ProactiveService messages, etc.)
        # Current implementation uses simple FIFO deletion, losing important info in long conversations
        # Example: 33-min demo with 25,000 token limit deleted ikura/kazunoko info from 18:34 at 18:52
        # Improvement ideas:
        # 1. Increase immediate_tokens setting (25,000 → 50,000 etc.)
        # 2. Message importance-based deletion priority control
        # 3. Deletion exclusion flag for ProactiveService messages
        while self._total_tokens > self.max_tokens and len(messages) > 1:
            messages.popleft()
            removed_tokens = self._token_counts.popleft()
            self._total_tokens -= removed_tokens
        
        removed_count = initial_count - len(messages)
        if removed_count > 0:
            logger.debug(f"Deleted {removed_count} messages (current tokens: {self._total_tokens})")
        
        return removed_count
    
    def clear(self) -> None:
        """Clear token management (for resource cleanup)"""
        self._token_counts.clear()
        self._total_tokens = 0
        self._encoding = None