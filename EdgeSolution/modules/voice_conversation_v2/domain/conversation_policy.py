#!/usr/bin/env python3
"""
ConversationPolicy - Business rules for conversation management
"""


class ConversationPolicy:
    """Manages business rules for conversation flow"""
    
    @staticmethod
    def is_exit_command(text: str) -> bool:
        """
        Determine if the text contains an exit command
        
        Args:
            text: Text to be evaluated
            
        Returns:
            True if text contains exit command, False otherwise
        """
        # TODO: Move hardcoded Japanese phrases to configuration file or Config class
        # TODO: Replace keyword matching with LLM-based intent detection agent
        #       to analyze conversation context and determine exit intent more accurately
        exit_phrases = [
            "さようなら", "さよなら", "バイバイ", "ばいばい",
            "おやすみ", "おやすみなさい", "またね", "じゃあね"
        ]
        return any(phrase in text for phrase in exit_phrases)