#!/usr/bin/env python3

import os
import time
import json
import subprocess
import logging
from datetime import datetime

import pytz
from azure.iot.device import IoTHubModuleClient, Message

JST = pytz.timezone('Asia/Tokyo')

def get_utc_timestamp():
    return datetime.utcnow().isoformat() + 'Z'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.module_client = None
        self.disk_threshold_warning = 70
        self.disk_threshold_critical = 80
        self.check_interval = 3600
        self.cleanup_interval = 21600
        self.last_cleanup = 0
        
    def init_module_client(self):
        try:
            self.module_client = IoTHubModuleClient.create_from_edge_environment()
            logger.info("IoT Hub module client initialized")
        except Exception as e:
            logger.error(f"Failed to create module client: {e}")
            
    def get_disk_usage(self):
        try:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                usage_str = parts[4].rstrip('%')
                return int(usage_str)
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return 0
            
    def cleanup_docker(self):
        logger.info("Starting Docker cleanup...")
        cleanup_commands = [
            ["docker", "container", "prune", "-f"],
            ["docker", "image", "prune", "-a", "-f", "--filter", "until=12h"],
            ["docker", "volume", "prune", "-f"],
            ["docker", "system", "prune", "-a", "-f", "--volumes"],
        ]
        
        for cmd in cleanup_commands:
            try:
                logger.info(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"Success: {result.stdout}")
                else:
                    logger.error(f"Failed: {result.stderr}")
            except Exception as e:
                logger.error(f"Error running {cmd}: {e}")

        # Journal log cleanup
        try:
            subprocess.run(
                ["journalctl", "--vacuum-size=50M"],
                capture_output=True,
                text=True
            )
            logger.info("Cleaned journal logs")
        except Exception as e:
            logger.error(f"Failed to clean journal logs: {e}")
            
    def send_telemetry(self, data):
        if self.module_client:
            try:
                message = Message(json.dumps(data))
                message.custom_properties["message-type"] = "system-telemetry"
                self.module_client.send_message_to_output(message, "telemetry")
                logger.info(f"Sent telemetry: {data}")
            except Exception as e:
                logger.error(f"Failed to send telemetry: {e}")
                
    def monitor_system(self):
        while True:
            try:
                # Check disk usage
                disk_usage = self.get_disk_usage()
                logger.info(f"Current disk usage: {disk_usage}%")
                
                # Send telemetry
                telemetry = {
                    "type": "system_telemetry",
                    "timestamp": get_utc_timestamp(),
                    "disk_usage_percent": disk_usage,
                    "device_id": os.getenv("IOTEDGE_DEVICEID", "unknown"),
                    "module_id": os.getenv("IOTEDGE_MODULEID", "system-monitor")
                }
                self.send_telemetry(telemetry)
                
                # Check warning levels
                current_time = time.time()
                if disk_usage >= self.disk_threshold_critical:
                    logger.warning(f"Disk usage critical: {disk_usage}%")
                    # Execute cleanup
                    if current_time - self.last_cleanup > 3600:
                        self.cleanup_docker()
                        self.last_cleanup = current_time

                        new_usage = self.get_disk_usage()
                        logger.info(f"Disk usage after cleanup: {new_usage}%")
                        telemetry["cleanup_performed"] = True
                        telemetry["disk_usage_after_cleanup"] = new_usage
                        self.send_telemetry(telemetry)
                elif disk_usage >= self.disk_threshold_warning:
                    logger.warning(f"Disk usage warning: {disk_usage}%")
                    
                # Scheduled cleanup (every 6 hours)
                if current_time - self.last_cleanup > self.cleanup_interval:
                    if disk_usage > 60:
                        logger.info("Performing scheduled cleanup...")
                        self.cleanup_docker()
                        self.last_cleanup = current_time
                        
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
            time.sleep(self.check_interval)

def main():
    logger.info("Starting System Monitor module...")
    monitor = SystemMonitor()
    monitor.init_module_client()
    
    try:
        monitor.monitor_system()
    except KeyboardInterrupt:
        logger.info("Module stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if monitor.module_client:
            monitor.module_client.shutdown()

if __name__ == "__main__":
    main()