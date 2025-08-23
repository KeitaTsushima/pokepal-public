"""
System Prompt Builder - Dedicated service for system prompt construction

This module handles system prompt construction processing.
Enables dynamic prompt generation including memory information
through integration with memory repository.
"""
import logging


class SystemPromptBuilderError(Exception):
    pass


class SystemPromptBuilder:
    """Specialized service for system prompt construction"""
    
    def __init__(self, memory_repository=None, config_loader=None) -> None:
        """
        Args:
            memory_repository: Memory repository (Infrastructure layer)
            config_loader: Configuration loader for prompt templates (required)
        
        Raises:
            ValueError: If config_loader is not provided
        """
        if not config_loader:
            raise ValueError("config_loader is required for SystemPromptBuilder")
        
        self._logger = logging.getLogger(__name__)
        self._memory_repository = memory_repository
        self._config_loader = config_loader
        
        self._logger.debug("SystemPromptBuilder initialized")
    
    def build_system_prompt(self) -> str:
        """
        Build system prompt with memory integration
        
        Returns:
            System prompt string with memory information
            
        Raises:
            SystemPromptBuilderError: When error occurs in prompt construction
            ValueError: When configuration is invalid
        """
        try:
            # Get base system prompt from config
            base_prompt = self._config_loader.get("llm.system_prompt")
            
            if not self._memory_repository:
                return base_prompt
                
            # Add memory information to base prompt
            memory_sections = self._build_memory_sections()
            
            if memory_sections:
                return f"{base_prompt}\n\n{memory_sections}"
            else:
                return base_prompt
            
        except Exception as e:
            error_msg = f"Failed to build system prompt: {e}"
            self._logger.error(error_msg)
            raise SystemPromptBuilderError(error_msg) from e
    
    def _build_memory_sections(self) -> str:
        """Build memory sections to append to base system prompt
        
        Returns:
            Formatted memory sections string, or empty string if no memory
            
        Raises:
            KeyError: If required configuration keys are missing
        """
        try:
            # Get templates from configuration
            format_templates = self._config_loader.get("llm.memory_format")
            memory_config = self._config_loader.get("memory.max_items_per_section")
            
            # Get memory data from repository
            memory = self._memory_repository.get_current_memory()
            memory_data = memory["memory"]
            
            # Build memory sections using unified processing
            prompt_parts = []
            memory_sections = [
                {
                    "data_key": "short_term_memory",
                    "template_key": "short_term_memory",
                    "source": memory_data,
                    "is_list": False
                },
                {
                    "data_key": "preferences",
                    "template_key": "preferences", 
                    "source": memory_data.get("user_context", {}),
                    "is_list": True
                },
                {
                    "data_key": "concerns",
                    "template_key": "concerns",
                    "source": memory_data.get("user_context", {}),
                    "is_list": True
                }
            ]
            
            for section in memory_sections:
                data = section["source"].get(section["data_key"])
                if not data:
                    continue
                    
                if section["is_list"]:
                    max_items = memory_config[section["data_key"]]
                    content = "、".join(data[:max_items])
                else:
                    content = data
                    
                template = format_templates[section["template_key"]]
                prompt_parts.append(template.format(content=content))
            
            result = "\n".join(prompt_parts)
            self._logger.info(f"Built memory sections: {len(prompt_parts)} sections, length={len(result)}")
            return result
            
        except Exception as e:
            self._logger.error(f"Failed to build memory sections: {e}")
            raise
