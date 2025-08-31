"""
Unit tests for IoTCommandAdapter
Tests command processing from IoT Hub
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import sys

# Mock azure.iot.device module
sys.modules['azure'] = MagicMock()
sys.modules['azure.iot'] = MagicMock()
sys.modules['azure.iot.device'] = MagicMock()

from adapters.input.iot_commands import IoTCommandAdapter


class TestIoTCommandAdapter:
    """Test class for IoTCommandAdapter"""
    
    @pytest.fixture
    def mock_module_client(self):
        """Mock IoTHubModuleClient"""
        client = Mock()
        client.on_twin_desired_properties_patch_received = None
        client.on_method_request_received = None
        return client
    
    @pytest.fixture
    def mock_config_loader(self, mock_module_client):
        """Mock ConfigLoader"""
        loader = Mock()
        loader.module_client = mock_module_client
        loader.update = Mock()
        loader.get = Mock(return_value={})
        loader.get_config = Mock(return_value={
            "llm": {"model": "gpt-4o-mini"},
            "stt": {"model": "whisper-1"}
        })
        return loader
    
    @pytest.fixture
    def mock_callback(self):
        """Mock callback function"""
        return Mock()
    
    @pytest.fixture
    def adapter(self, mock_config_loader):
        """Adapter under test"""
        return IoTCommandAdapter(mock_config_loader)
    
    def test_init(self, adapter, mock_module_client, mock_config_loader):
        """Test initialization"""
        assert adapter.config_loader == mock_config_loader
        assert adapter.update_callbacks == {}
        assert hasattr(adapter, 'method_handlers')
        assert hasattr(adapter, 'start_time')
        # Check if handlers are set
        assert mock_module_client.on_twin_desired_properties_patch_received is not None
        assert mock_module_client.on_method_request_received is not None
    
    def test_init_no_iot_hub(self):
        """Initialization without IoT Hub connection"""
        mock_config_loader = Mock()
        mock_config_loader.module_client = None
        adapter = IoTCommandAdapter(mock_config_loader)
        assert adapter.config_loader.module_client is None
    
    def test_register_update_callback(self, adapter, mock_callback):
        """Register update callback"""
        adapter.register_update_callback("scheduler", mock_callback)
        assert adapter.update_callbacks["scheduler"] == mock_callback
    
    def test_handle_twin_update(self, adapter, mock_config_loader, mock_callback):
        """Handle Twin update"""
        # Register callback
        adapter.register_update_callback("scheduler", mock_callback)
        
        # Twin update data
        twin_patch = {
            "scheduler": {
                "enabled": True,
                "morning_greeting": "09:00"
            },
            "llm": {
                "temperature": 0.8
            }
        }
        
        # Process Twin update
        adapter._handle_twin_update(twin_patch)
        
        # Check if settings were updated
        mock_config_loader.update.assert_called_once_with(twin_patch)
        
        # Check if callback was called
        mock_callback.assert_called_once_with({
            "enabled": True,
            "morning_greeting": "09:00"
        })
    
    def test_handle_twin_update_no_callback(self, adapter, mock_config_loader):
        """Twin update without callback"""
        twin_patch = {
            "no_voice_sleep_threshold": 10
        }
        
        # Processed without error
        adapter._handle_twin_update(twin_patch)
        mock_config_loader.update.assert_called_once_with(twin_patch)
    
    def test_handle_twin_update_error(self, adapter, mock_config_loader):
        """Handle Twin update error"""
        mock_config_loader.update.side_effect = Exception("Update error")
        
        # No exception thrown even if error occurs
        adapter._handle_twin_update({"test": "value"})
    
    def test_handle_method_request_get_status(self, adapter, mock_module_client):
        """Handle get_status method request"""
        # Method request
        request = Mock()
        request.name = "get_status"
        request.payload = None
        request.request_id = "test-request-id"
        
        # Process request
        result = adapter._handle_method_request(request)
        
        # Check result
        assert result[0] == 200
        assert "status" in result[1]
        assert "config" in result[1]
        assert "connections" in result[1]
        assert "uptime_seconds" in result[1]
    
    def test_handle_method_request_update_config(self, adapter, mock_config_loader):
        """Handle config update method request"""
        # Method request
        request = Mock()
        request.name = "update_config"
        request.payload = json.dumps({
            "llm": {"temperature": 0.9},
            "new_setting": "value"
        })
        
        # Process request
        result = adapter._handle_method_request(request)
        
        # Check if config was updated
        mock_config_loader.update.assert_called_once_with({
            "llm": {"temperature": 0.9},
            "new_setting": "value"
        })
        
        # Check result
        assert result[0] == 200
        assert "message" in result[1]
    
    def test_handle_method_request_get_memory_status(self, adapter):
        """Handle get memory status method request"""
        # Method request
        request = Mock()
        request.name = "get_memory_status"
        request.payload = None
        
        # Process request
        result = adapter._handle_method_request(request)
        
        # Check result (when memory_manager not registered)
        assert result[0] == 200
        assert "status" in result[1]
        assert result[1]["status"] == "error"
    
    def test_handle_method_request_unknown(self, adapter):
        """Handle unknown method request"""
        # Method request
        request = Mock()
        request.name = "unknown_method"
        request.payload = None
        
        # Process request
        result = adapter._handle_method_request(request)
        
        # Check result
        assert result[0] == 404
        assert "error" in result[1]
        assert result[1]["error"] == "Method not found"
    
    def test_handle_method_request_error(self, adapter):
        """Handle method request error"""
        # Method request
        request = Mock()
        request.name = "update_config"
        request.payload = "invalid json"
        
        # Process request
        result = adapter._handle_method_request(request)
        
        # Check error result
        assert result[0] == 400
        assert "error" in result[1]
        assert "Invalid JSON payload" in result[1]["error"]