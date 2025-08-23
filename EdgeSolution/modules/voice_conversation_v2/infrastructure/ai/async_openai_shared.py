"""
Shared AsyncOpenAI Transport
Provides shared HTTP transport for AsyncOpenAI clients to optimize connection reuse
"""
import os
import asyncio
import httpx
import logging
from typing import Optional
from openai import AsyncOpenAI

from ..security.async_key_vault import get_async_key_vault


class SharedAsyncOpenAI:
    """Shared AsyncOpenAI client with transport reuse and API key injection"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Shared HTTP transport with optimized settings
        self._http_client: Optional[httpx.AsyncClient] = None
        # No base client needed - we create new clients with real API keys
        self._initialized = False
        
        # Semaphore controls for concurrent requests
        self._stt_semaphore = asyncio.Semaphore(
            int(os.getenv("STT_MAX_CONCURRENCY", "1"))
        )
        self._llm_semaphore = asyncio.Semaphore(
            int(os.getenv("LLM_MAX_CONCURRENCY", "3"))
        )
    
    async def _ensure_initialized(self):
        """Lazy initialization of shared HTTP transport"""
        if self._initialized:
            return
        
        try:
            # Create shared HTTP client with optimized settings
            self._http_client = httpx.AsyncClient(
                # Timeout configuration (connect/read/write/pool)
                timeout=httpx.Timeout(
                    connect=5.0,    # Connection timeout
                    read=120.0,     # Read timeout (Whisper can take time)
                    write=30.0,     # Write timeout
                    pool=5.0        # Pool timeout
                ),
                # Connection limits and keep-alive
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=20
                ),
                headers={"Connection": "keep-alive"},
                # HTTP/2 support
                http2=True
            )
            
            # Don't create base client here - we'll create new clients with real API keys
            self._initialized = True
            self.logger.info("SharedAsyncOpenAI initialized - HTTP transport with connection pooling ready")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize SharedAsyncOpenAI: {e}")
            raise
    
    async def _get_openai_client(self, secret_name: str) -> AsyncOpenAI:
        """
        Internal method to get AsyncOpenAI client with API key from Key Vault
        
        Args:
            secret_name: Name of the OpenAI API key secret in Key Vault
            
        Returns:
            AsyncOpenAI client with API key from Key Vault
        """
        await self._ensure_initialized()
        
        kv_client = await get_async_key_vault()
        api_key = await kv_client.get_secret(secret_name)
        
        # Create new client with real API key (HTTP client is shared)
        return AsyncOpenAI(
            api_key=api_key,
            http_client=self._http_client
        )
    
    async def get_stt_client(self, secret_name: str) -> AsyncOpenAI:
        """
        Get AsyncOpenAI client for STT with semaphore control and API key from Key Vault
        
        Args:
            secret_name: Name of the OpenAI API key secret in Key Vault
            
        Returns:
            AsyncOpenAI client with injected API key
        """
        async with self._stt_semaphore:
            return await self._get_openai_client(secret_name)
    
    async def get_llm_client(self, secret_name: str) -> AsyncOpenAI:
        """
        Get AsyncOpenAI client for LLM with semaphore control and API key from Key Vault
        
        Args:
            secret_name: Name of the OpenAI API key secret in Key Vault
            
        Returns:
            AsyncOpenAI client with injected API key
        """
        async with self._llm_semaphore:
            return await self._get_openai_client(secret_name)
    
    async def close(self):
        try:
            if self._http_client:
                await self._http_client.aclose()
            
            self._initialized = False
            self.logger.info("SharedAsyncOpenAI transport closed")
            
        except Exception as e:
            self.logger.error(f"Error closing SharedAsyncOpenAI: {e}")


# Global singleton instance for transport sharing
_shared_openai_instance: Optional[SharedAsyncOpenAI] = None


async def get_shared_openai() -> SharedAsyncOpenAI:
    """Get global SharedAsyncOpenAI instance"""
    global _shared_openai_instance
    
    if _shared_openai_instance is None:
        _shared_openai_instance = SharedAsyncOpenAI()
    
    return _shared_openai_instance

async def cleanup_shared_openai():
    """Cleanup global SharedAsyncOpenAI instance"""
    global _shared_openai_instance
    
    if _shared_openai_instance:
        await _shared_openai_instance.close()
        _shared_openai_instance = None