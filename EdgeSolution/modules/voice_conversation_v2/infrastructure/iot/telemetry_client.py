"""
IoT Telemetry Client - Infrastructure Layer
Responsible for converting conversation data to IoT Hub format and sending

TODO: User ID information transmission support (v2 refactoring remaining task)
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict
from azure.iot.device import Message


class IoTTelemetryClient:
    """Client for sending conversation data to IoT Hub"""
    
    def __init__(self, iot_client, config_loader):
        """Initialize IoTTelemetryClient with Clean Architecture compliance
        
        Args:
            iot_client: IoT Hub client for message sending
            config_loader: ConfigLoader instance for dynamic configuration access
        """
        self.iot_client = iot_client
        self.config_loader = config_loader
        self.logger = logging.getLogger(__name__)
        
        self.device_id = self._get_required_env("IOTEDGE_DEVICEID")
        self.module_id = self._get_required_env("IOTEDGE_MODULEID")

        self.logger.info("IoT Telemetry initialized: device_id=%s, module_id=%s", self.device_id, self.module_id)

    def _get_required_env(self, var_name: str) -> str:
        value = os.getenv(var_name)
        if not value:
            raise ValueError(f"{var_name} environment variable is required for IoT module identification")
        return value
    
    def send_conversation(self, speaker: str, text: str) -> None:
        if not self.iot_client:
            self.logger.debug("Skipping transmission due to IoT Hub disconnection")
            return
        
        data = {
            "messageType": self.config_loader.get('telemetry.message_type'),
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "module_id": self.module_id,
            "data": {
                "speaker": speaker,
                "text": text
            }
        }
        
        for attempt in range(self.config_loader.get('telemetry.retry_attempts')):
            try:
                message = Message(json.dumps(data, ensure_ascii=False))
                message.content_encoding = self.config_loader.get('telemetry.content_encoding')
                message.content_type = self.config_loader.get('telemetry.content_type')
                message.custom_properties["messageType"] = self.config_loader.get('telemetry.message_type')
                
                self.iot_client.send_message_to_output(message, self.config_loader.get('telemetry.output_name'))
                log_limit = self.config_loader.get('telemetry.log_text_limit')
                self.logger.info("Conversation data transmission successful: %s: %s...", speaker, text[:log_limit])
                return
                
            except (ConnectionError, TimeoutError, OSError) as e:
                retry_attempts = self.config_loader.get('telemetry.retry_attempts')
                if attempt < retry_attempts - 1:
                    self.logger.warning("Conversation data transmission failed (attempt %d/%d): %s", attempt + 1, retry_attempts, e)
                    time.sleep(self.config_loader.get('telemetry.retry_delay'))
                else:
                    retry_attempts = self.config_loader.get('telemetry.retry_attempts')
                    self.logger.error("Conversation data transmission failed (after %d attempts): %s", retry_attempts, e)

            except (ValueError, TypeError, json.JSONEncodeError) as e:
                self.logger.error("Conversation data format error: %s", e)
                break
            
            except Exception as e:
                self.logger.error("Unexpected error in conversation data transmission: %s", e)
                break
    

    
    
