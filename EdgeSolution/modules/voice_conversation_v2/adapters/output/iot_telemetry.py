"""
IoT Telemetry Adapter
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


class IoTTelemetryAdapter:
    """Adapter for sending conversation data to IoT Hub"""
    
    def __init__(self, iot_client, config):
        self.iot_client = iot_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self.message_type = config.get("telemetry.message_type", "conversation")
        self.content_type = config.get("telemetry.content_type", "application/json")
        self.content_encoding = config.get("telemetry.content_encoding", "utf-8")
        self.output_name = config.get("telemetry.output_name", "output1")
        self.log_text_limit = config.get("telemetry.log_text_limit", 50)
        self.retry_attempts = config.get("telemetry.retry_attempts", 3)
        self.retry_delay = config.get("telemetry.retry_delay", 1.0)
        
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
            "messageType": self.message_type,
            "timestamp": datetime.now().isoformat(),
            "device_id": self.device_id,
            "module_id": self.module_id,
            "data": {
                "speaker": speaker,
                "text": text
            }
        }
        
        for attempt in range(self.retry_attempts):
            try:
                message = Message(json.dumps(data, ensure_ascii=False))
                message.content_encoding = self.content_encoding
                message.content_type = self.content_type
                message.custom_properties["messageType"] = self.message_type
                
                self.iot_client.send_message_to_output(message, self.output_name)
                self.logger.info("Conversation data transmission successful: %s: %s...", speaker, text[:self.log_text_limit])
                return
                
            except (ConnectionError, TimeoutError, OSError) as e:
                if attempt < self.retry_attempts - 1:
                    self.logger.warning("Conversation data transmission failed (attempt %d/%d): %s", attempt + 1, self.retry_attempts, e)
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("Conversation data transmission failed (after %d attempts): %s", self.retry_attempts, e)

            except (ValueError, TypeError, json.JSONEncodeError) as e:
                self.logger.error("Conversation data format error: %s", e)
                break
            
            except Exception as e:
                self.logger.error("Unexpected error in conversation data transmission: %s", e)
                break
    

    
    
