"""
Memory Repository - Memory management implementation

Loads daily-generated memory files and generates system prompts.
Integrates with Azure Functions MemoryGenerator for cloud-generated memory files.

TODO: user_id support
- Current: device_id-based memory file management
- Future: device_id + user_id for per-user memory management
- Memory file format: {"device_id": "XXX", "user_id": "YYY", "memory": {...}}
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class MemoryRepository:
    """Memory management repository for daily conversation summaries"""
    
    def __init__(self, memory_dir: str = "/app/memories", retention_days: int = 7):
        self.memory_dir = memory_dir
        self.retention_days = retention_days
        self.logger = logger
        self._cached_memory = None  # Cache for pre-loaded memory
        self._cache_date = None  # Date of cached memory
        
        # Create directory if it doesn't exist
        if not os.path.exists(self.memory_dir):
            try:
                os.makedirs(self.memory_dir, exist_ok=True)
                self.logger.info("Created memory directory: %s", self.memory_dir)
            except Exception as e:
                self.logger.error("Failed to create memory directory: %s", e)
        
        # Cleanup old files during initialization
        self.cleanup_old_memories()
        
    def preload_memory(self) -> None:
        """
        Pre-load the latest memory file into cache at startup
        """
        self._cached_memory = self._load_latest_memory()
        self._cache_date = datetime.now().strftime("%Y%m%d")
        if self._cached_memory:
            self.logger.info("Memory pre-loaded and cached for fast access")
    
    def get_current_memory(self) -> Dict[str, Any]:
        """
        Load the latest memory file (search from today backwards)
        Uses cache if available and current
        
        Returns:
            Memory data (including short-term, medium-term, and long-term memory)
        """
        # Use cached memory if it's from today
        today_str = datetime.now().strftime("%Y%m%d")
        if self._cached_memory and self._cache_date == today_str:
            self.logger.debug("Using cached memory")
            return self._cached_memory
        
        # Otherwise, load from disk
        memory = self._load_latest_memory()
        if memory:
            self._cached_memory = memory
            self._cache_date = today_str
        return memory
    
    def _load_latest_memory(self) -> Dict[str, Any]:
        """
        Internal method to load the latest memory file from disk
        """
        # Search for files from today to past retention period
        today = datetime.now()
        
        for days_ago in range(self.retention_days):  # Search within retention period
            date = today - timedelta(days=days_ago)
            date_str = date.strftime("%Y%m%d")
            file_path = os.path.join(self.memory_dir, f"memory_{date_str}.json")
            
            if os.path.exists(file_path):
                self.logger.info(f"Found memory file: {file_path}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        memory_data = json.load(f)
                    self.logger.info(f"Successfully loaded memory from {date_str}")
                    return memory_data
                except Exception as e:
                    self.logger.error(f"Failed to load memory file {file_path}: {e}")
                    continue
        
        # Memory file not found case
        self.logger.warning(f"No memory file found in the last {self.retention_days} days")
        return {
            "device_id": "unknown",
            "generated_at": datetime.now().isoformat(),
            "memory": {
                "short_term_memory": "過去の会話記録がありません",
                "medium_term_memory": {"keywords": [], "events": []},
                "user_context": {"preferences": [], "concerns": [], "routine": []}
            }
        }    
    
    def download_memory_from_blob(self, blob_url: str, sas_token: str) -> bool:
        """
        Download memory file from Azure Blob Storage
        
        Args:
            blob_url: Blob URL
            sas_token: SAS token for authentication
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract filename from URL
            parsed_url = urlparse(blob_url)
            filename = os.path.basename(parsed_url.path)
            
            # Build URL with SAS token
            download_url = f"{blob_url}?{sas_token}"
            
            # Download file
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            # Save locally
            file_path = os.path.join(self.memory_dir, filename)
            os.makedirs(self.memory_dir, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Memory file downloaded successfully: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download memory file: {e}")
            return False
    
    def cleanup_old_memories(self) -> int:
        """Delete old memory files beyond retention period"""
        if not os.path.exists(self.memory_dir):
            return 0
            
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        
        for filename in os.listdir(self.memory_dir):
            if filename.startswith("memory_") and filename.endswith(".json"):
                try:
                    date_str = filename[7:15]
                    if datetime.strptime(date_str, "%Y%m%d") < cutoff_date:
                        os.remove(os.path.join(self.memory_dir, filename))
                        deleted_count += 1
                except (ValueError, IndexError, OSError):
                    pass  # Skip invalid files
        
        return deleted_count
