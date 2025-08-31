"""
Unit tests for ConfigLoader
Tests configuration file loading and Module Twin synchronization
"""
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
import json
import sys

# Mock azure.iot.device module
sys.modules['azure'] = MagicMock()
sys.modules['azure.iot'] = MagicMock()
sys.modules['azure.iot.device'] = MagicMock()

from infrastructure.config.config_loader import ConfigLoader


class TestConfigLoader:
    """Test class for ConfigLoader"""
    
    @pytest.fixture
    def mock_module_client(self):
        """Mock IoTHubModuleClient"""
        client = Mock()
        client.get_twin = Mock(return_value={
            "desired": {
                "llm": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.8
                },
                "stt": {
                    "model": "whisper-1"
                },
                "no_voice_sleep_threshold": 10,
                "scheduler": {
                    "enabled": True,
                    "morning_greeting": "08:00"
                }
            }
        })
        return client
    
    @pytest.fixture
    def loader(self, mock_module_client):
        """Loader under test"""
        with patch('azure.iot.device.IoTHubModuleClient') as mock_class:
            mock_class.create_from_edge_environment.return_value = mock_module_client
            return ConfigLoader()
    
    def test_init_default_config(self):
        """Initialization with default config"""
        with patch('azure.iot.device.IoTHubModuleClient') as mock_class:
            mock_class.create_from_edge_environment.side_effect = Exception("No IoT Hub")
            loader = ConfigLoader()
            
            # Check default settings
            assert loader.config["llm"]["model"] == "gpt-4o-mini"
            assert loader.config["llm"]["temperature"] == 0.7
            assert loader.config["stt"]["model"] == "whisper-1"
            assert loader.config["no_voice_sleep_threshold"] == 5
    
    def test_load_from_file(self, loader):
        """Load config from file"""
        config_data = {
            "llm": {"model": "gpt-4", "temperature": 0.9},
            "stt": {"model": "whisper-large"},
            "custom_setting": "test"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(config_data))):
            with patch("os.path.exists", return_value=True):
                loaded_config = loader.load_from_file("config.json")
        
        assert loaded_config["llm"]["model"] == "gpt-4"
        assert loaded_config["llm"]["temperature"] == 0.9
        assert loaded_config["custom_setting"] == "test"
    
    def test_load_from_file_not_exists(self, loader):
        """When file does not exist"""
        with patch("os.path.exists", return_value=False):
            loaded_config = loader.load_from_file("nonexistent.json")
        
        assert loaded_config == {}
    
    def test_sync_with_twin(self, loader, mock_module_client):
        """Synchronization with Module Twin"""
        # Execute sync
        loader.sync_with_twin()
        
        # Check if Twin get was called
        mock_module_client.get_twin.assert_called_once()
        
        # Check if settings were updated
        assert loader.config["llm"]["model"] == "gpt-4o-mini"
        assert loader.config["llm"]["temperature"] == 0.8
        assert loader.config["no_voice_sleep_threshold"] == 10
        assert loader.config["scheduler"]["enabled"] is True
    
    def test_sync_with_twin_error(self, loader, mock_module_client):
        """Handling Twin sync errors"""
        mock_module_client.get_twin.side_effect = Exception("Twin error")
        
        # Does not throw exception even if error occurs
        loader.sync_with_twin()
        
        # Settings are not changed
        assert loader.config["llm"]["model"] == "gpt-4o-mini"
        assert loader.config["llm"]["temperature"] == 0.7
    
    def test_get_config(self, loader):
        """Get configuration"""
        config = loader.get_config()
        
        assert isinstance(config, dict)
        assert "llm" in config
        assert "stt" in config
        assert "tts" in config
    
    def test_get_specific_config(self, loader):
        """Get specific key configuration"""
        llm_config = loader.get("llm")
        assert llm_config["model"] == "gpt-4o-mini"
        
        threshold = loader.get("no_voice_sleep_threshold")
        assert threshold == 5
        
        # Non-existent key
        missing = loader.get("nonexistent", default="default_value")
        assert missing == "default_value"
    
    def test_update_config(self, loader):
        """Update configuration"""
        new_settings = {
            "llm": {"model": "gpt-4", "temperature": 0.5},
            "new_key": "new_value"
        }
        
        loader.update(new_settings)
        
        assert loader.config["llm"]["model"] == "gpt-4"
        assert loader.config["llm"]["temperature"] == 0.5
        assert loader.config["new_key"] == "new_value"
        # Existing settings are preserved
        assert loader.config["stt"]["model"] == "whisper-1"
    
    def test_merge_config(self, loader):
        """Merge configuration"""
        original_config = {"a": 1, "b": {"c": 2, "d": 3}}
        updates = {"b": {"c": 4, "e": 5}, "f": 6}
        
        merged = loader._merge_config(original_config, updates)
        
        assert merged["a"] == 1
        assert merged["b"]["c"] == 4  # Updated
        assert merged["b"]["d"] == 3  # Preserved
        assert merged["b"]["e"] == 5  # Added
        assert merged["f"] == 6  # Added