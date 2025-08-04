"""
System Prompt Builder - Dedicated service for system prompt construction

This module handles system prompt construction processing.
Enables dynamic prompt generation including memory information
through integration with memory repository.
"""
import logging
from typing import Optional

from domain.conversation import ConversationConfig


class SystemPromptBuilderError(Exception):
    pass


class SystemPromptBuilder:
    """Specialized service for system prompt construction"""
    
    def __init__(self, memory_repository=None) -> None:
        """
        Args:
            memory_repository: Memory repository (Infrastructure layer)
        """
        self._logger = logging.getLogger(__name__)
        self._memory_repository = memory_repository
        
        self._logger.debug("SystemPromptBuilder initialized")
    
    def build_system_prompt(self, config: ConversationConfig) -> str:
        """
        Build system prompt
        
        Args:
            config: Conversation configuration (ConversationConfig)
            
        Returns:
            System prompt string
            
        Raises:
            SystemPromptBuilderError: When error occurs in prompt construction
            ValueError: When configuration is invalid
        """
        try:
            if self._memory_repository:
                return self._build_memory_based_prompt()
            
            return self._build_default_prompt(config)
            
        except Exception as e:
            error_msg = f"Failed to build system prompt: {e}"
            self._logger.error(error_msg)
            raise SystemPromptBuilderError(error_msg) from e
    
    def _build_memory_based_prompt(self) -> str:
        try:
            prompt = self._memory_repository.build_system_prompt()
            
            if not prompt or not isinstance(prompt, str):
                raise ValueError("Memory repository returned invalid prompt")
            
            self._logger.info(
                f"Built memory-based system prompt: length={len(prompt)}, "
                f"preview={prompt[:100]}..."
            )
            return prompt
            
        except Exception as e:
            self._logger.error(f"Failed to build memory-based prompt: {e}")
            raise
    
    def _build_default_prompt(self, config: ConversationConfig) -> str:
        if not config or not hasattr(config, 'default_system_prompt'):
            raise ValueError("Invalid conversation config: missing default_system_prompt")
        
        base_prompt = config.default_system_prompt
        if not base_prompt:
            raise ValueError("Default system prompt is empty")
        
        memory_instruction = self._get_memory_instruction()
        full_prompt = base_prompt + memory_instruction
        
        self._logger.info(
            f"Built default system prompt: length={len(full_prompt)}, "
            f"base_length={len(base_prompt)}"
        )
        return full_prompt
    
    def _get_memory_instruction(self) -> str:
        """
        Get instruction text for immediate memory functionality
        
        # TODO: Externalize immediate memory instruction text configuration
        # Move this string as an attribute of ConversationConfig to make it configurable
        # Then this method becomes unnecessary and can be retrieved in one line with config.immediate_memory_instruction
        
        Returns:
            Text explaining memory functionality
        """
        return """

あなたは現在進行中の会話の内容を記憶しており、直前のやり取りを参照しながら自然な会話を続けることができます。
ユーザーから「さっき何を話した？」「前に言ったことは？」などと聞かれた場合は、会話履歴を参照して適切に答えてください。"""
    
    @property
    def has_memory_repository(self) -> bool:
        return self._memory_repository is not None