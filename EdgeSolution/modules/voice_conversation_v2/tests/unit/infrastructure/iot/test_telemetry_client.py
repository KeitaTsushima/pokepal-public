"""
Unit tests for IoTTelemetryClient
Tests conversation data transmission to IoT Hub
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from infrastructure.iot.telemetry_client import IoTTelemetryClient


class TestIoTTelemetryClient:
    """Test class for IoTTelemetryClient"""
    
    @pytest.fixture
    def mock_iot_client(self):
        """Mock IoT Hub client"""
        client = Mock()
        client.send_message = Mock()
        client.is_connected = True
        return client
    
    @pytest.fixture
    def adapter(self, mock_iot_client):
        """Adapter under test"""
        return IoTTelemetryClient(iot_client=mock_iot_client)
    
    def test_init(self, adapter, mock_iot_client):
        """Test initialization"""
        assert adapter.iot_client == mock_iot_client
    
    @patch('adapters.output.iot_telemetry.datetime')
    def test_send_conversation(self, mock_datetime, adapter, mock_iot_client):
        """Test conversation data transmission"""
        # Setup
        mock_now = datetime(2025, 7, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        # Execute
        adapter.send_conversation("user", "こんにちは")
        
        # Verify
        mock_iot_client.send_message.assert_called_once()
        call_args = mock_iot_client.send_message.call_args[0]
        assert call_args[0] == "conversation"
        
        data = call_args[1]
        assert data["speaker"] == "user"
        assert data["text"] == "こんにちは"
        assert data["timestamp"] == mock_now.isoformat()
    
    def test_send_conversation_not_connected(self, adapter, mock_iot_client):
        """Test transmission when not connected"""
        # Setup
        mock_iot_client.is_connected = False
        
        # Execute
        adapter.send_conversation("user", "こんにちは")
        
        # Verify
        mock_iot_client.send_message.assert_not_called()
    
    def test_send_conversation_error_handling(self, adapter, mock_iot_client):
        """Test transmission error handling"""
        # Setup
        mock_iot_client.send_message.side_effect = Exception("Send error")
        
        # Execute (should not crash even if exception occurs)
        adapter.send_conversation("user", "こんにちは")
        
        # Verify
        mock_iot_client.send_message.assert_called_once()
    
    def test_send_telemetry(self, adapter, mock_iot_client):
        """Test generic telemetry transmission"""
        # Execute
        adapter.send_telemetry("health", {"status": "ok"})
        
        # Verify
        mock_iot_client.send_message.assert_called_once_with("health", {"status": "ok"})
    
    def test_is_connected(self, adapter, mock_iot_client):
        """Test connection status check"""
        # Connected
        assert adapter.is_connected() is True
        
        # Not connected
        mock_iot_client.is_connected = False
        assert adapter.is_connected() is False