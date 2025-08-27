"""
TwinSync - IoT Hub Module Twin management

Handles startup reporting, memory updates from cloud, and conversation service management.
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from infrastructure.iot.connection_manager import IoTConnectionManager

logger = logging.getLogger(__name__)


class TwinSync:
    """Minimal twin management class - only what main.py actually uses"""
    
    def __init__(self, config_loader, memory_repository=None, iot_connection_manager: Optional[IoTConnectionManager] = None):
        self.config_loader = config_loader
        self.memory_repository = memory_repository
        self.iot_connection_manager = iot_connection_manager
        self.start_time = datetime.utcnow()
        
        if self.iot_connection_manager:
            logger.debug("TwinSync initialized with dedicated IoT connection manager")
        else:
            logger.warning("TwinSync initialized with deprecated ConfigLoader IoT client")
    
    def report_startup(self) -> None:
        client = self.iot_connection_manager.get_client() if self.iot_connection_manager else self.config_loader.module_client
        if not client:
            return
        
        try:
            device_id = os.environ.get("IOTEDGE_DEVICEID", "unknown")
            module_id = os.environ.get("IOTEDGE_MODULEID", "unknown")
            
            reported_props = {
                "startup": {
                    "timestamp": self.start_time.isoformat(),
                    "device_id": device_id,
                    "module_id": module_id,
                    "request_conversation_restore": True
                }
            }
            
            client.patch_twin_reported_properties(reported_props)
            logger.info("Reported startup to twin for device %s", device_id)
            
        except Exception as e:
            logger.error("Failed to report startup: %s", e)
    
    def receive_memory_summary(self, memory_update):
        logger.info("Received memory update: %s", memory_update)
        
        # Handle None memory_update
        if memory_update is None:
            logger.warning("Received None memory_update, skipping")
            return
            
        blob_url = memory_update.get("url")
        sas_token = memory_update.get("sas")
        
        if blob_url and sas_token and self.memory_repository:
            logger.info("Processing memory update from cloud...")
            success = self.memory_repository.download_memory_from_blob(blob_url, sas_token)
            
            if success:
                logger.info("Memory file updated successfully")
            else:
                logger.error("Failed to update memory file")
        else:
            logger.warning("Memory update skipped: missing parameters or repository")
