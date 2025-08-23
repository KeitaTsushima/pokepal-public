"""
Async Key Vault Client
Async implementation for Azure Key Vault access with TTL caching and connection reuse
"""
import os
import time
import asyncio
import logging
from collections import defaultdict
from typing import Optional

from azure.identity.aio import CertificateCredential
from azure.keyvault.secrets.aio import SecretClient


class AsyncKeyVaultClient:
    """Async Key Vault client with TTL caching and secret deduplication"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self._url = os.environ.get("KEY_VAULT_URL")
        self._tenant = os.environ.get("AZURE_TENANT_ID")
        self._client_id = os.environ.get("AZURE_CLIENT_ID")
        self._cert_path = os.environ.get("AZURE_CLIENT_CERTIFICATE_PATH")
        
        if not all([self._url, self._tenant, self._client_id, self._cert_path]):
            cert_exists = os.path.exists(self._cert_path) if self._cert_path else False
            raise ValueError(
                f"Key Vault configuration incomplete. Please ensure all required environment variables are set:\n"
                f"  KEY_VAULT_URL: {self._url or 'NOT SET'}\n"
                f"  AZURE_TENANT_ID: {self._tenant or 'NOT SET'}\n"
                f"  AZURE_CLIENT_ID: {self._client_id or 'NOT SET'}\n"
                f"  AZURE_CLIENT_CERTIFICATE_PATH: {self._cert_path or 'NOT SET'}\n"
                f"  Certificate file exists: {cert_exists}\n"
                f"\nTo set up Key Vault authentication:\n"
                f"  1. Create Service Principal and certificate (see docs/daily-logs/2025-08-18.md)\n"
                f"  2. Place certificate at /etc/iotedge/kvcerts/pokepal-kv.pfx\n"
                f"  3. Set environment variables in deployment.template.json\n"
                f"  4. Deploy with updated configuration"
            )
        
        self._ttl = int(os.getenv("KV_SECRET_TTL_SEC", "60"))        
        self._locks = defaultdict(asyncio.Lock)
        self._cache = {}
        self._credential = None
        self._client = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Lazy initialization of Azure credentials and client"""
        if self._initialized:
            return
        
        try:
            self._credential = CertificateCredential(
                tenant_id=self._tenant,
                client_id=self._client_id,
                certificate_path=self._cert_path
            )
            
            # Create async SecretClient without custom retry policy
            self._client = SecretClient(
                vault_url=self._url,
                credential=self._credential
            )
            
            self._initialized = True
            self.logger.info("AsyncKeyVaultClient initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AsyncKeyVaultClient: {e}")
            raise
    
    async def get_secret(self, secret_name: str) -> str:
        """
        Get secret from Key Vault with TTL caching and deduplication
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Secret value as string
            
        Raises:
            ValueError: If secret_name is empty
            Exception: If Key Vault access fails
        """
        if not secret_name:
            raise ValueError("Secret name cannot be empty")
        
        await self._ensure_initialized()
        
        start_time = time.perf_counter()
        now = time.monotonic()
        
        # Check TTL cache first
        if self._ttl > 0:
            cached_entry = self._cache.get(secret_name)
            if cached_entry and cached_entry[1] > now:
                cache_time = time.perf_counter() - start_time
                self.logger.debug(f"Secret '{secret_name}' retrieved from cache ({cache_time:.3f}s)")
                return cached_entry[0]
        
        # Use lock to prevent duplicate concurrent requests for same secret
        async with self._locks[secret_name]:
            # Double-check cache after acquiring lock
            if self._ttl > 0:
                cached_entry = self._cache.get(secret_name)
                if cached_entry and cached_entry[1] > now:
                    cache_time = time.perf_counter() - start_time
                    self.logger.debug(f"Secret '{secret_name}' retrieved from cache after lock ({cache_time:.3f}s)")
                    return cached_entry[0]
            
            try:
                # Fetch from Key Vault
                secret = await self._client.get_secret(secret_name)
                secret_value = secret.value
                
                # Update cache if TTL is enabled
                if self._ttl > 0:
                    expire_time = now + self._ttl
                    self._cache[secret_name] = (secret_value, expire_time)
                
                fetch_time = time.perf_counter() - start_time
                self.logger.debug(f"Secret '{secret_name}' fetched from Key Vault ({fetch_time:.3f}s)")
                
                return secret_value
                
            except Exception as e:
                fetch_time = time.perf_counter() - start_time
                self.logger.error(f"Failed to get secret '{secret_name}' from Key Vault ({fetch_time:.3f}s): {e}")
                raise
    
    async def warmup_token_only(self, timeout_sec: float = 5.0) -> bool:
        """
        Warm up AAD authentication and TLS connection without retrieving secret values.
        
        Args:
            timeout_sec: Timeout for token acquisition
            
        Returns:
            True if successful, False if failed (best-effort)
        """
        try:
            await self._ensure_initialized()
            
            # Get AAD token for Key Vault scope to warm up authentication
            KV_SCOPE = "https://vault.azure.net/.default"
            await asyncio.wait_for(
                self._credential.get_token(KV_SCOPE),
                timeout=timeout_sec
            )
            
            self.logger.info("[warmup] Key Vault token acquired successfully")
            return True
            
        except Exception as e:
            self.logger.warning(f"[warmup] Key Vault token acquisition failed (best-effort): {e}")
            return False
    
    async def close(self):
        try:
            if self._client:
                await self._client.close()
            if self._credential:
                await self._credential.close()
            
            self._cache.clear()
            self._locks.clear()
            self._initialized = False
            
            self.logger.info("AsyncKeyVaultClient closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing AsyncKeyVaultClient: {e}")



_async_kv_instance: Optional[AsyncKeyVaultClient] = None


async def get_async_key_vault() -> AsyncKeyVaultClient:
    global _async_kv_instance
    
    if _async_kv_instance is None:
        _async_kv_instance = AsyncKeyVaultClient()
    
    return _async_kv_instance


async def cleanup_async_key_vault():
    global _async_kv_instance
    
    if _async_kv_instance:
        await _async_kv_instance.close()
        _async_kv_instance = None