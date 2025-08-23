"""
IoT Hub Connection Management

Manages IoT Hub Module Client connection, connection state, and lifecycle.
"""
import logging
import traceback
from typing import Optional

from azure.iot.device import IoTHubModuleClient


class IoTConnectionManager:
    """IoT Hub connection management specialized class"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.module_client: Optional = None
        self._is_connected = False
        
    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.module_client is not None
    
    def initialize_client(self) -> bool:
        if self._is_connected and self.module_client:
            self.logger.debug("IoT Hub Module Client already initialized")
            return True
            
        try:
            self.logger.info("Initializing IoT Hub Module Client from edge environment...")
            self.module_client = IoTHubModuleClient.create_from_edge_environment()
            self.logger.info("IoT Hub Module Client initialized, ready to connect")
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize IoT Hub Module Client: %s", e)
            self.logger.error("Traceback: %s", traceback.format_exc())
            self.module_client = None
            return False
    
    def connect(self) -> bool:
        if not self.module_client:
            if not self.initialize_client():
                return False
        
        if self._is_connected:
            self.logger.debug("Already connected to IoT Hub")
            return True
            
        try:
            self.logger.info("Attempting to connect to IoT Hub...")
            self.module_client.connect()
            self.logger.info("Successfully connected to IoT Hub")
            self._is_connected = True
            return True
            
        except Exception as e:
            self.logger.error("Failed to connect to IoT Hub: %s", e)
            self.module_client = None
            self._is_connected = False
            return False
    
    def disconnect(self) -> None:
        if not self._is_connected or not self.module_client:
            self.logger.debug("IoT Hub not connected, skipping disconnect")
            return
            
        try:
            self.logger.info("Disconnecting from IoT Hub...")
            self.module_client.disconnect()
            self.logger.info("Successfully disconnected from IoT Hub")

        except Exception as e:
            self.logger.warning("Error during IoT Hub disconnect: %s", e)

        finally:
            self._is_connected = False
            self.module_client = None
    
    def get_client(self):
        if not self.is_connected:
            self.logger.warning("IoT Hub not connected, attempting reconnection...")
            if not self.connect():
                self.logger.warning("IoT Hub reconnection failed, returning None")
                return None
        return self.module_client
    
    def cleanup(self) -> None:
        try:
            self.disconnect()
            self.logger.info("IoTConnectionManager cleanup completed")
        except Exception as e:
            self.logger.error("IoTConnectionManager cleanup error: %s", e)
