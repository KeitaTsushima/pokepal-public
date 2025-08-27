"""
OpenAI API Client
Concrete implementation for LLM response generation with secure Key Vault integration
"""
import os
import logging
import re
from typing import Optional, Dict, Any, List
from domain.message import Message
from .async_openai_shared import get_shared_openai


class LLMClient:
    """LLM client using OpenAI API"""
    
    def __init__(self, config_loader):
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        # Store secret name for on-demand Key Vault access
        self.openai_secret_name = os.environ['OPENAI_SECRET_NAME']
        
        self.logger.info("LLMClient initialized successfully")
    
    async def complete_chat(self, messages: List[Message], system_prompt: str) -> Optional[str]:
        try:
            api_messages = self._convert_to_api_format(messages, system_prompt)
            
            # Get current configuration dynamically
            model = self.config_loader.get('llm.model')
            max_tokens = self.config_loader.get('llm.max_tokens')
            temperature = self.config_loader.get('llm.temperature')
            
            # Get shared OpenAI client with semaphore control
            shared_openai = await get_shared_openai()
            client = await shared_openai.get_llm_client(self.openai_secret_name)
            
            response = await client.chat.completions.create(
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            reply = self._normalize(response.choices[0].message.content)
            
            self.logger.info("AI response generation completed: %s...", reply[:50])
            
            return reply
            
        except Exception as e:
            self.logger.error("Response generation error: %s", e)
            return None
    
    async def stream_chat_completion(self, messages: List[Message], system_prompt: str):
        try:
            api_messages = self._convert_to_api_format(messages, system_prompt)
            final_buf = []
            
            # Get current configuration dynamically
            model = self.config_loader.get('llm.model')
            max_tokens = self.config_loader.get('llm.max_tokens')
            temperature = self.config_loader.get('llm.temperature')
            
            # Get shared OpenAI client with semaphore control
            shared_openai = await get_shared_openai()
            client = await shared_openai.get_llm_client(self.openai_secret_name)
            
            stream = await client.chat.completions.create(
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True}  # Add usage stats for debugging
            )
            
            chunk_count = 0
            async for chunk in stream:
                chunk_count += 1
                try:
                    delta = chunk.choices[0].delta.content
                except Exception:
                    delta = None
                    
                if delta:
                    final_buf.append(delta)
                    yield {"type": "delta", "text": delta}
                    
        except Exception as e:
            self.logger.error("Streaming response error: %s", e)
        finally:
            final_text = self._normalize("".join(final_buf)) if final_buf else ""
            yield {"type": "final", "text": final_text}
    
    def _normalize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        t = text.replace("\n", " ").replace("\r", " ")
        return re.sub(r"\s+", " ", t).strip()
    
    def _ensure_single_system_message(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        system_messages = [msg for msg in messages if isinstance(msg, dict) and msg.get('role') == 'system']
        
        if len(system_messages) > 1:
            self.logger.error("Multiple system messages detected (%d). Using first one only to maintain conversation.", len(system_messages))
            other_messages = [msg for msg in messages if msg.get('role') != 'system']
            return [system_messages[0]] + other_messages
        
        return messages
    
    def _convert_to_api_format(self, messages: List[Dict[str, str]], system_prompt: str) -> List[Dict[str, str]]:
        messages = self._ensure_single_system_message(messages)
        
        api_messages = []
        has_system_message = False
        
        for msg in messages:
            if not isinstance(msg, dict):
                raise TypeError(f"Expected dict, got {type(msg).__name__}: {msg}")
            
            if not all(key in msg for key in ['role', 'content']):
                raise ValueError(f"Message missing required keys 'role' or 'content': {msg}")
            
            if msg.get('role') == 'system':
                has_system_message = True
                self.logger.info("Using system message from conversation service: length=%d", len(msg['content']))
                self.logger.info("First 100 chars: %s...", msg['content'][:100])
                
            api_messages.append(msg)
        
        if not has_system_message:
            system_message = {
                'role': 'system',
                'content': system_prompt
            }
            api_messages.insert(0, system_message)
            self.logger.info("No system message found, using provided system prompt")
        
        return api_messages
    
