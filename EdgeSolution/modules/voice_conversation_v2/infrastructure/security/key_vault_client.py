"""
Azure Key Vault Client

Provides Key Vault integration for secure secret management.
"""
import logging
import os
from typing import Optional
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, CertificateCredential

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """Client for retrieving secrets from Azure Key Vault"""
    
    def __init__(self, vault_url: Optional[str] = None):
        self.vault_url = vault_url or os.environ.get("KEY_VAULT_URL")
        self._client: Optional[SecretClient] = None
        
        if not self.vault_url:
            logger.warning("Key Vault URL not found in environment variables. Key Vault integration disabled, falling back to environment variable API key.")
    
    def _get_client(self) -> Optional[SecretClient]:
        """Get SecretClient (lazy initialization)"""
        if self._client is not None:
            return self._client
            
        if not self.vault_url:
            return None
            
        try:
            # Priority 1: Service Principal with Certificate (IoT Edge environment)
            tenant_id = os.environ.get("AZURE_TENANT_ID")
            client_id = os.environ.get("AZURE_CLIENT_ID")
            cert_path = os.environ.get("AZURE_CLIENT_CERTIFICATE_PATH")
            
            if tenant_id and client_id and cert_path:
                if os.path.exists(cert_path):
                    logger.info("Using CertificateCredential for Key Vault access...")
                    # PEM format: no password required (certificate + private key in single file)
                    credential = CertificateCredential(
                        tenant_id=tenant_id,
                        client_id=client_id,
                        certificate_path=cert_path
                    )
                else:
                    logger.error(
                        f"Certificate file not found at {cert_path}\n"
                        f"Please ensure the certificate is properly mounted.\n"
                        f"Expected location: /etc/iotedge/kvcerts/pokepal-kv.pfx"
                    )
                    return None
            elif os.environ.get("IOTEDGE_DEVICEID"):
                logger.info("Attempting to use Managed Identity for Key Vault access...")
                credential = ManagedIdentityCredential()
            else:
                logger.info("Using DefaultAzureCredential for Key Vault access...")
                # Disable IMDS to prevent timeouts in non-Azure environments
                credential = DefaultAzureCredential(exclude_managed_identity_credential=True)
            
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            logger.info(f"Successfully created Key Vault client for {self.vault_url}")
            return self._client
            
        except Exception as e:
            logger.error(f"Failed to create Key Vault client: {e}")
            return None
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        client = self._get_client()
        if not client:
            logger.warning(f"Key Vault client not available for {secret_name}")
            return None
            
        try:
            secret = client.get_secret(secret_name)
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            return None
    
    def close(self):
        """Close the client"""
        if self._client:
            try:
                self._client.close()
                logger.info("Key Vault client closed")
            except Exception as e:
                logger.error(f"Error closing Key Vault client: {e}")
