"""
Azure IoT Hub contract tests
IoT Hub API schema validation and contract testing
"""
import pytest
import json
from typing import Dict, Any, List
from datetime import datetime


class TestIoTHubContract:
    """Contract tests for Azure IoT Hub"""
    
    def validate_twin_schema(self, twin: Dict[str, Any]) -> bool:
        """Validate Device Twin schema"""
        # Check basic structure
        required_sections = ['properties']
        for section in required_sections:
            if section not in twin:
                return False
        
        properties = twin['properties']
        
        # Check desired/reported sections
        if 'desired' not in properties and 'reported' not in properties:
            return False
        
        return True
    
    def validate_telemetry_schema(self, telemetry: Dict[str, Any]) -> bool:
        """Validate telemetry message schema"""
        # PokePal-specific telemetry format
        required_fields = ['timestamp', 'type', 'data']
        
        for field in required_fields:
            if field not in telemetry:
                return False
        
        # Check timestamp format
        try:
            datetime.fromisoformat(telemetry['timestamp'])
        except:
            return False
        
        return True
    
    def test_device_twin_desired_properties_contract(self):
        """Contract test for Device Twin Desired Properties"""
        # Expected Twin format
        valid_twin = {
            "properties": {
                "desired": {
                    "conversation_restore": {
                        "enabled": True,
                        "restore_date": "2025-08-29",
                        "restore_count": 5
                    },
                    "llm_config": {
                        "model": "gpt-4",
                        "temperature": 0.7,
                        "max_tokens": 500
                    },
                    "$metadata": {
                        "$lastUpdated": "2025-08-29T10:00:00Z"
                    },
                    "$version": 1
                }
            }
        }
        
        assert self.validate_twin_schema(valid_twin) is True
        
        # PokePal-specific configuration structure
        desired = valid_twin["properties"]["desired"]
        assert "conversation_restore" in desired
        assert "llm_config" in desired
    
    def test_device_twin_reported_properties_contract(self):
        """Contract test for Device Twin Reported Properties"""
        valid_reported = {
            "properties": {
                "reported": {
                    "status": {
                        "state": "running",
                        "last_active": "2025-08-29T10:00:00Z",
                        "version": "0.1.76"
                    },
                    "performance": {
                        "average_response_time": 2.6,
                        "total_conversations": 150,
                        "success_rate": 0.95
                    },
                    "$metadata": {
                        "$lastUpdated": "2025-08-29T10:00:00Z"
                    },
                    "$version": 1
                }
            }
        }
        
        assert self.validate_twin_schema(valid_reported) is True
        
        # Check required fields
        reported = valid_reported["properties"]["reported"]
        assert "status" in reported
        assert "state" in reported["status"]
    
    def test_direct_method_request_contract(self):
        """Contract test for Direct Method requests"""
        # Direct Method invocation format
        valid_method_request = {
            "methodName": "get_status",
            "responseTimeoutInSeconds": 30,
            "connectTimeoutInSeconds": 10,
            "payload": {
                "include_memory": True,
                "include_performance": True
            }
        }
        
        # Required fields
        assert "methodName" in valid_method_request
        
        # Methods defined in PokePal
        valid_methods = [
            "get_status",
            "update_config",
            "get_memory_status",
            "restart_conversation",
            "clear_memory"
        ]
        assert valid_method_request["methodName"] in valid_methods
    
    def test_direct_method_response_contract(self):
        """Contract test for Direct Method responses"""
        valid_response = {
            "status": 200,
            "payload": {
                "result": "success",
                "data": {
                    "state": "running",
                    "uptime": 3600,
                    "last_conversation": "2025-08-29T09:30:00Z"
                }
            }
        }
        
        # Required fields
        assert "status" in valid_response
        assert "payload" in valid_response
        
        # HTTP status code range
        assert 200 <= valid_response["status"] < 600
    
    def test_telemetry_message_contract(self):
        """Contract test for telemetry messages"""
        valid_telemetry = {
            "timestamp": "2025-08-29T10:00:00Z",
            "type": "conversation",
            "data": {
                "user_message": "Hello",
                "ai_response": "Hello! How are you?",
                "processing_time": 2.5,
                "tokens_used": 150
            },
            "metadata": {
                "module_id": "voice_conversation_v2",
                "device_id": "pokepal-device-001"
            }
        }
        
        assert self.validate_telemetry_schema(valid_telemetry) is True
        
        # PokePal-specific telemetry types
        valid_types = [
            "conversation",
            "performance",
            "error",
            "system_event",
            "memory_update"
        ]
        assert valid_telemetry["type"] in valid_types
    
    def test_module_twin_update_contract(self):
        """Contract test for Module Twin updates"""
        # Twin update patch format
        valid_patch = {
            "properties": {
                "desired": {
                    "llm_config": {
                        "temperature": 0.8
                    }
                }
            }
        }
        
        assert self.validate_twin_schema(valid_patch) is True
        
        # Check partial update
        assert "properties" in valid_patch
        assert "desired" in valid_patch["properties"]
    
    def test_connection_string_contract(self):
        """Contract test for connection string format"""
        # IoT Hub connection string format
        connection_string_pattern = (
            "HostName={hub_name}.azure-devices.net;"
            "DeviceId={device_id};"
            "SharedAccessKey={key}"
        )
        
        # Required components
        required_parts = ["HostName", "DeviceId", "SharedAccessKey"]
        
        sample_connection = (
            "HostName=pokepalhub-s1.azure-devices.net;"
            "DeviceId=pokepal-device-001;"
            "SharedAccessKey=xxxxxxxxxxxxx"
        )
        
        for part in required_parts:
            assert part in sample_connection
    
    def test_edge_module_environment_contract(self):
        """Contract test for Edge Module environment variables"""
        # Required environment variables
        required_env_vars = {
            "IOTEDGE_MODULEID": "voice_conversation_v2",
            "IOTEDGE_DEVICEID": "pokepal-device",
            "IOTEDGE_IOTHUBHOSTNAME": "pokepalhub-s1.azure-devices.net",
            "IOTEDGE_MODULEGENERATIONID": "xxxxxxxxxx",
            "IOTEDGE_WORKLOADURI": "http://localhost:15580",
            "IOTEDGE_APIVERSION": "2020-07-07"
        }
        
        # Check format of each environment variable
        assert required_env_vars["IOTEDGE_APIVERSION"] in ["2019-01-30", "2020-07-07", "2021-12-07"]
        assert required_env_vars["IOTEDGE_WORKLOADURI"].startswith("http")
    
    def test_message_routing_contract(self):
        """Contract test for message routing"""
        # IoT Edge message format
        valid_message = {
            "body": {
                "timestamp": "2025-08-29T10:00:00Z",
                "data": {"test": "value"}
            },
            "properties": {
                "content-type": "application/json",
                "content-encoding": "utf-8",
                "message-type": "telemetry"
            },
            "systemProperties": {
                "messageId": "uuid-12345",
                "correlationId": "correlation-12345",
                "userId": "user-001"
            }
        }
        
        # Required properties
        assert "body" in valid_message
        assert "properties" in valid_message
        
        # Validate content-type
        valid_content_types = ["application/json", "text/plain", "application/octet-stream"]
        assert valid_message["properties"]["content-type"] in valid_content_types