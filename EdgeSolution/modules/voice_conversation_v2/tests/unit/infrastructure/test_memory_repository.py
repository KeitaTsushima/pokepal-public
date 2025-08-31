"""
Unit tests for MemoryRepository
Tests memory management repository
"""
import pytest
import json
import os
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime, timedelta
from infrastructure.memory.memory_repository import MemoryRepository


class TestMemoryRepository:
    """Test class for MemoryRepository"""
    
    @pytest.fixture
    def repository(self):
        """Repository for testing"""
        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                with patch('os.listdir', return_value=[]):  # For cleanup_old_memories
                    repo = MemoryRepository(memory_dir="/tmp/test_memories", retention_days=7)
                    return repo
    
    def test_init(self):
        """Test initialization"""
        with patch('os.path.exists', return_value=False):
            with patch('os.makedirs') as mock_makedirs:
                with patch.object(MemoryRepository, 'cleanup_old_memories'):
                    repo = MemoryRepository(memory_dir="/tmp/test_memories", retention_days=7)
                    
                    assert repo.memory_dir == "/tmp/test_memories"
                    assert repo.retention_days == 7
                    assert repo._cached_memory is None
                    assert repo._cache_date is None
                    mock_makedirs.assert_called_once_with("/tmp/test_memories", exist_ok=True)
    
    def test_init_directory_exists(self):
        """Test initialization when directory already exists"""
        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs') as mock_makedirs:
                with patch.object(MemoryRepository, 'cleanup_old_memories'):
                    repo = MemoryRepository(memory_dir="/tmp/test_memories")
                    mock_makedirs.assert_not_called()
    
    def test_init_directory_creation_failure(self):
        """Test directory creation failure"""
        with patch('os.path.exists', return_value=False):
            with patch('os.makedirs', side_effect=Exception("Permission denied")):
                with patch.object(MemoryRepository, 'cleanup_old_memories'):
                    # Exception doesn't propagate (logged instead)
                    repo = MemoryRepository(memory_dir="/tmp/test_memories")
                    assert repo.memory_dir == "/tmp/test_memories"
    
    def test_preload_memory(self, repository):
        """Test memory preloading"""
        test_memory = {
            "device_id": "test_device",
            "memory": {
                "short_term_memory": "Test memory",
                "user_context": {}
            }
        }
        
        with patch.object(repository, '_load_latest_memory', return_value=test_memory):
            repository.preload_memory()
            
            assert repository._cached_memory == test_memory
            assert repository._cache_date is not None  # Verify date is set
    
    def test_get_current_memory_from_cache(self, repository):
        """Test getting memory from cache"""
        test_memory = {"device_id": "test", "memory": {}}
        repository._cached_memory = test_memory
        repository._cache_date = datetime.now().strftime("%Y%m%d")
        
        result = repository.get_current_memory()
        assert result == test_memory
    
    def test_get_current_memory_cache_expired(self, repository):
        """Test cache expiration"""
        old_memory = {"device_id": "old", "memory": {}}
        new_memory = {"device_id": "new", "memory": {}}
        
        repository._cached_memory = old_memory
        repository._cache_date = "20250101"  # Old date
        
        with patch.object(repository, '_load_latest_memory', return_value=new_memory):
            result = repository.get_current_memory()
            assert result == new_memory
            assert repository._cached_memory == new_memory
    
    def test_load_latest_memory_success(self, repository):
        """Test successful loading of latest memory file"""
        test_memory = {
            "device_id": "test_device",
            "memory": {
                "short_term_memory": "Yesterday's conversation",
                "user_context": {
                    "preferences": ["music", "reading"],
                    "concerns": ["health"]
                }
            }
        }
        
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        file_path = f"/tmp/test_memories/memory_{date_str}.json"
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(test_memory))):
                result = repository._load_latest_memory()
                assert result == test_memory
    
    def test_load_latest_memory_not_found(self, repository):
        """Test when memory file is not found"""
        with patch('os.path.exists', return_value=False):
            result = repository._load_latest_memory()
            
            assert result["device_id"] == "unknown"
            assert "memory" in result
            assert result["memory"]["short_term_memory"] == "No past conversation records"
    
    def test_load_latest_memory_past_file(self, repository):
        """Test loading past memory files"""
        test_memory = {"device_id": "test", "memory": {}}
        
        with patch('os.path.exists') as mock_exists:
            # Today and yesterday's files don't exist, 2 days ago file exists
            mock_exists.side_effect = [False, False, True]
            
            with patch('builtins.open', mock_open(read_data=json.dumps(test_memory))):
                result = repository._load_latest_memory()
                assert result == test_memory
    
    def test_load_latest_memory_json_error(self, repository):
        """Test JSON loading error"""
        invalid_json = "{ invalid json"
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=invalid_json)):
                result = repository._load_latest_memory()
                # Returns default memory on error
                assert result["device_id"] == "unknown"
    
    def test_cleanup_old_memories(self, repository):
        """Test cleanup of old memory files"""
        today = datetime.now()
        old_date = today - timedelta(days=10)
        recent_date = today - timedelta(days=3)
        
        old_file = f"memory_{old_date.strftime('%Y%m%d')}.json"
        recent_file = f"memory_{recent_date.strftime('%Y%m%d')}.json"
        
        with patch('os.path.exists', return_value=True):  # For directory existence check
            with patch('os.listdir', return_value=[old_file, recent_file]):
                with patch('os.remove') as mock_remove:
                    with patch('os.path.join', side_effect=lambda d, f: f"{d}/{f}"):
                        deleted_count = repository.cleanup_old_memories()
                        # Only old file is deleted
                        mock_remove.assert_called_once_with(f"/tmp/test_memories/{old_file}")
                        assert deleted_count == 1
    
    def test_cleanup_old_memories_error_handling(self, repository):
        """Test error handling during cleanup"""
        old_file = "memory_20240101.json"
        
        with patch('os.path.exists', return_value=True):
            with patch('os.listdir', return_value=[old_file]):
                with patch('os.remove', side_effect=OSError("Permission denied")):
                    # Doesn't crash on error (OSError is handled)
                    deleted_count = repository.cleanup_old_memories()
                    assert deleted_count == 0  # Failed to delete, so 0
    
    def test_download_memory_from_blob_success(self, repository):
        """Test successful memory download from Blob storage"""
        test_memory = {"device_id": "test", "memory": {}}
        mock_response = Mock()
        mock_response.json.return_value = test_memory
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get', return_value=mock_response):
            with patch('builtins.open', mock_open()) as mock_file:
                result = repository.download_memory_from_blob(
                    "https://test.blob.core.windows.net/memories/memory_20250827.json",
                    "sv=2020-08-04&st=2025-08-27T00:00:00Z&se=2025-08-28T00:00:00Z&sr=b&sp=r&sig=test"
                )
                assert result == True
                mock_file.assert_called()
    
    def test_download_memory_from_blob_failure(self, repository):
        """Test failed memory download from Blob storage"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        
        with patch('requests.get', return_value=mock_response):
            result = repository.download_memory_from_blob(
                "https://test.blob.core.windows.net/memories/memory_20250827.json",
                "sv=2020-08-04&st=2025-08-27T00:00:00Z&se=2025-08-28T00:00:00Z&sr=b&sp=r&sig=test"
            )
            assert result == False
    
    def test_download_memory_from_blob_exception(self, repository):
        """Test exception handling during Blob download"""
        with patch('requests.get', side_effect=Exception("Connection error")):
            result = repository.download_memory_from_blob(
                "https://test.blob.core.windows.net/memories/memory_20250827.json",
                "sv=2020-08-04&st=2025-08-27T00:00:00Z&se=2025-08-28T00:00:00Z&sr=b&sp=r&sig=test"
            )
            assert result == False