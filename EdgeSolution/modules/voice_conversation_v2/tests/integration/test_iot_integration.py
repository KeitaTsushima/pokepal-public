"""
IoT Hub Integration Tests

Tests Module Twin updates, command processing, telemetry sending,
and other IoT Hub integration features.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json
from datetime import datetime

from adapters.input.iot_commands import IoTCommandAdapter
from infrastructure.iot.telemetry_client import IoTTelemetryClient
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.config.twin_sync import TwinSync


class TestIoTIntegration:
    """IoT Hub integration tests"""
    
    @pytest.fixture
    def mock_iot_client(self):
        """Mock IoT Hub client"""
        client = Mock()
        client.connect.return_value = None
        client.disconnect.return_value = None
        client.send_message.return_value = None
        client.patch_twin_reported_properties.return_value = None
        return client
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        loader = Mock(spec=ConfigLoader)
        loader.get.side_effect = lambda key, default=None: {
            "module.iot_hub_connection_string": "test-connection-string",
            "telemetry.enabled": True,
            "telemetry.interval": 60
        }.get(key, default)
        loader.update.return_value = None
        loader.get_config.return_value = {"test": "config"}
        return loader
    
    def test_module_twin_update_flow(self, mock_iot_client, mock_config_loader):
        """Test Module Twin update flow"""
        # Create IoTCommandAdapter
        with patch('adapters.input.iot_commands.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            command_adapter = IoTCommandAdapter(mock_config_loader)
            
            # Register Twin update callback
            update_callback = Mock()
            command_adapter.register_update_callback(update_callback)
            
            # Simulate Twin update
            twin_patch = {
                "conversation": {
                    "sleep_threshold": 10,
                    "greeting_interval_hours": 12
                },
                "vad": {
                    "mode": 2,
                    "speech_threshold": 25
                }
            }
            
            command_adapter.handle_twin_update(twin_patch)
            
            # Verify: ConfigLoader was updated
            mock_config_loader.update.assert_called_once_with(twin_patch)
            
            # Verify: Callback was called
            update_callback.assert_called_once_with(twin_patch)
    
    def test_iot_command_processing(self, mock_iot_client, mock_config_loader):
        """Test IoT command processing"""
        with patch('adapters.input.iot_commands.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            command_adapter = IoTCommandAdapter(mock_config_loader)
            
            # Set command handler
            mock_iot_client.on_method_request_received = None
            
            # Test restart command
            method_request = Mock()
            method_request.name = "restart"
            method_request.payload = None
            
            response = command_adapter.handle_method_request(method_request)
            
            assert response.status == 200
            result = json.loads(response.payload)
            assert result["status"] == "success"
            assert result["message"] == "Module will restart"
            
            # Test update_config command
            method_request.name = "update_config"
            method_request.payload = json.dumps({
                "llm": {"temperature": 0.8}
            })
            
            response = command_adapter.handle_method_request(method_request)
            
            assert response.status == 200
            result = json.loads(response.payload)
            assert result["status"] == "success"
            
            # Verify settings were updated
            mock_config_loader.update.assert_called()
    
    def test_telemetry_sending_flow(self, mock_iot_client):
        """Test telemetry sending flow"""
        with patch('adapters.output.iot_telemetry.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            telemetry = IoTTelemetryClient()
            
            # Send conversation data
            conversation_data = {
                "timestamp": datetime.now().isoformat(),
                "user_message": "Hello",
                "ai_response": "Hello! Nice weather today.",
                "processing_time": 1.5,
                "metadata": {
                    "no_voice_count": 0,
                    "is_sleeping": False
                }
            }
            
            telemetry.send_conversation(conversation_data)
            
            # Verify: Message was sent
            mock_iot_client.send_message.assert_called_once()
            sent_message = mock_iot_client.send_message.call_args[0][0]
            sent_data = json.loads(sent_message.data)
            
            assert sent_data["user_message"] == "Hello"
            assert sent_data["ai_response"] == "Hello! Nice weather today."
            assert sent_data["processing_time"] == 1.5
    
    def test_health_check_reporting(self, mock_iot_client):
        """Test health check reporting"""
        with patch('infrastructure.config.twin_sync.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            twin_sync = TwinSync()
            
            # Update health check settings
            health_config = {
                "enabled": True,
                "interval_minutes": 5
            }
            twin_sync.update_health_check(health_config)
            
            # Report health status
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage_mb": 150,
                    "conversation_count": 10,
                    "error_count": 0,
                    "uptime_hours": 24
                }
            }
            
            twin_sync.report_health_status(health_status)
            
            # Verify: Reported Properties were updated
            mock_iot_client.patch_twin_reported_properties.assert_called()
            reported = mock_iot_client.patch_twin_reported_properties.call_args[0][0]
            
            assert "health_status" in reported
            assert reported["health_status"]["status"] == "healthy"
            assert "metrics" in reported["health_status"]
    
    def test_twin_sync_full_flow(self, mock_iot_client, mock_config_loader):
        """Test complete Twin sync flow"""
        with patch('infrastructure.config.twin_sync.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            # Initial Module Twin data
            mock_twin = {
                "desired": {
                    "conversation": {
                        "sleep_mode_enabled": True,
                        "sleep_threshold": 5
                    },
                    "scheduler": {
                        "enabled": True,
                        "morning_greeting": "08:00",
                        "evening_greeting": "20:00"
                    },
                    "health_check": {
                        "enabled": True,
                        "interval_minutes": 10
                    }
                }
            }
            mock_iot_client.get_twin.return_value = mock_twin
            
            twin_sync = TwinSync()
            
            # Test scheduler update
            twin_sync.update_scheduler(mock_twin["desired"]["scheduler"])
            
            # Test health check update
            twin_sync.update_health_check(mock_twin["desired"]["health_check"])
            
            # Test custom property sync
            custom_props = {
                "module_version": "2.0.0",
                "last_restart": datetime.now().isoformat()
            }
            twin_sync.sync_custom_properties(custom_props)
            
            # Verify: All properties were reported
            calls = mock_iot_client.patch_twin_reported_properties.call_args_list
            assert len(calls) >= 1
            
            # Check last call
            last_reported = calls[-1][0][0]
            assert "module_version" in last_reported
            assert last_reported["module_version"] == "2.0.0"
    
    def test_error_handling_and_recovery(self, mock_iot_client, mock_config_loader):
        """Test error handling and recovery"""
        with patch('adapters.output.iot_telemetry.IoTHubModuleClient') as MockIoTClient:
            # Simulate connection error
            mock_iot_client.send_message.side_effect = Exception("Connection lost")
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            telemetry = IoTTelemetryClient()
            
            # Should not crash on error
            conversation_data = {
                "timestamp": datetime.now().isoformat(),
                "user_message": "test",
                "ai_response": "test response"
            }
            
            # Returns False on error
            result = telemetry.send_conversation(conversation_data)
            assert result is False
            
            # Simulate reconnection
            mock_iot_client.send_message.side_effect = None
            mock_iot_client.send_message.return_value = None
            
            # Retry successful
            result = telemetry.send_conversation(conversation_data)
            assert result is True
    
    def test_batch_telemetry_sending(self, mock_iot_client):
        """Test batch telemetry sending"""
        with patch('adapters.output.iot_telemetry.IoTHubModuleClient') as MockIoTClient:
            MockIoTClient.create_from_connection_string.return_value = mock_iot_client
            
            telemetry = IoTTelemetryClient()
            
            # Multiple conversation data
            conversations = []
            for i in range(5):
                conversations.append({
                    "timestamp": datetime.now().isoformat(),
                    "user_message": f"Message{i}",
                    "ai_response": f"Response{i}",
                    "sequence_number": i
                })
            
            # Send each conversation
            for conv in conversations:
                telemetry.send_conversation(conv)
            
            # Verify: Sent 5 times
            assert mock_iot_client.send_message.call_count == 5
            
            # Verify sending order
            for i, call in enumerate(mock_iot_client.send_message.call_args_list):
                sent_data = json.loads(call[0][0].data)
                assert sent_data["sequence_number"] == i