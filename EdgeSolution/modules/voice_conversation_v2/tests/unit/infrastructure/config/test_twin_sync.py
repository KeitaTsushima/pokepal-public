"""
Unit tests for TwinSync
Tests Module Twin synchronization and health checks
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
from datetime import datetime, timedelta

# Mock azure.iot.device module
sys.modules['azure'] = MagicMock()
sys.modules['azure.iot'] = MagicMock()
sys.modules['azure.iot.device'] = MagicMock()

from infrastructure.config.twin_sync import TwinSync


class TestTwinSync:
    """Test class for TwinSync"""
    
    @pytest.fixture
    def mock_module_client(self):
        """Mock IoTHubModuleClient"""
        client = Mock()
        client.patch_twin_reported_properties = Mock()
        return client
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        loader = Mock()
        loader.get = Mock(side_effect=lambda key, default=None: {
            "scheduler.enabled": True,
            "scheduler.morning_greeting": "08:00",
            "health_check.enabled": True,
            "health_check.interval_minutes": 30
        }.get(key, default))
        return loader
    
    @pytest.fixture
    def twin_sync(self, mock_module_client, mock_config_loader):
        """TwinSync under test"""
        with patch('azure.iot.device.IoTHubModuleClient') as mock_class:
            mock_class.create_from_edge_environment.return_value = mock_module_client
            return TwinSync(mock_config_loader)
    
    def test_init(self, twin_sync, mock_module_client, mock_config_loader):
        """Test initialization"""
        assert twin_sync.module_client == mock_module_client
        assert twin_sync.config_loader == mock_config_loader
        assert twin_sync.last_health_check is not None
    
    def test_init_no_iot_hub(self, mock_config_loader):
        """Initialization without IoT Hub connection"""
        with patch('azure.iot.device.IoTHubModuleClient') as mock_class:
            mock_class.create_from_edge_environment.side_effect = Exception("No IoT Hub")
            twin_sync = TwinSync(mock_config_loader)
            assert twin_sync.module_client is None
    
    def test_update_scheduler_enabled(self, twin_sync, mock_module_client):
        """Update scheduler settings (enabled)"""
        scheduler_config = {
            "enabled": True,
            "morning_greeting": "09:00",
            "evening_greeting": "20:00"
        }
        
        twin_sync.update_scheduler(scheduler_config)
        
        # Check if Twin reported properties were updated
        mock_module_client.patch_twin_reported_properties.assert_called_once()
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        assert reported_props["scheduler"]["enabled"] is True
        assert reported_props["scheduler"]["morning_greeting"] == "09:00"
    
    def test_update_scheduler_disabled(self, twin_sync, mock_module_client):
        """Update scheduler settings (disabled)"""
        scheduler_config = {
            "enabled": False
        }
        
        twin_sync.update_scheduler(scheduler_config)
        
        # Check if Twin reported properties were updated
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        assert reported_props["scheduler"]["enabled"] is False
    
    def test_update_health_check(self, twin_sync, mock_module_client):
        """Update health check settings"""
        health_config = {
            "enabled": True,
            "interval_minutes": 60
        }
        
        twin_sync.update_health_check(health_config)
        
        # Check if Twin reported properties were updated
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        assert reported_props["health_check"]["enabled"] is True
        assert reported_props["health_check"]["interval_minutes"] == 60
    
    def test_report_health_status(self, twin_sync, mock_module_client):
        """Report health status"""
        twin_sync.report_health_status()
        
        # Check if Twin reported properties were updated
        mock_module_client.patch_twin_reported_properties.assert_called_once()
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        
        assert "health" in reported_props
        assert reported_props["health"]["status"] == "healthy"
        assert "timestamp" in reported_props["health"]
        assert "uptime_seconds" in reported_props["health"]
    
    def test_should_report_health_true(self, twin_sync, mock_config_loader):
        """When health check is needed"""
        # Set last health check to 31 minutes ago
        twin_sync.last_health_check = datetime.utcnow() - timedelta(minutes=31)
        
        assert twin_sync.should_report_health() is True
    
    def test_should_report_health_false(self, twin_sync, mock_config_loader):
        """When health check is not needed"""
        # Set last health check to 10 minutes ago
        twin_sync.last_health_check = datetime.utcnow() - timedelta(minutes=10)
        
        assert twin_sync.should_report_health() is False
    
    def test_should_report_health_disabled(self, twin_sync, mock_config_loader):
        """When health check is disabled"""
        mock_config_loader.get.return_value = False
        
        assert twin_sync.should_report_health() is False
    
    def test_report_error(self, twin_sync, mock_module_client):
        """Test error reporting"""
        error_message = "Test error occurred"
        
        twin_sync.report_error(error_message)
        
        # Check if Twin reported properties were updated
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        assert reported_props["health"]["status"] == "error"
        assert reported_props["health"]["error"] == error_message
    
    def test_sync_custom_properties(self, twin_sync, mock_module_client):
        """Sync custom properties"""
        custom_props = {
            "version": "1.0.0",
            "custom_setting": "value"
        }
        
        twin_sync.sync_custom_properties(custom_props)
        
        # Check if Twin reported properties were updated
        reported_props = mock_module_client.patch_twin_reported_properties.call_args[0][0]
        assert reported_props["version"] == "1.0.0"
        assert reported_props["custom_setting"] == "value"
    
    def test_no_module_client_operations(self, twin_sync):
        """Operations without Module Client"""
        twin_sync.module_client = None
        
        # Executes without error
        twin_sync.update_scheduler({"enabled": True})
        twin_sync.update_health_check({"enabled": True})
        twin_sync.report_health_status()
        twin_sync.report_error("test")