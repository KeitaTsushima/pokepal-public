"""
Configuration File and Module Twin Loading and Management

This module handles centralized configuration management.
Priority: Environment Variables (if explicitly set) > Runtime Config (dynamic detection) > Module Twin > Local Config File > Default Config

#TODO: DEPRECATION NOTICE: IoT-related functionality is planned to migrate to infrastructure.iot.connection_manager.IoTConnectionManager.
"""
import json
import logging
import os
import threading
import time
import warnings
from typing import Dict, Any, Optional


class ConfigLoader:
    """Configuration loading and management class"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self._get_default_config()
        self.runtime_config = {}
        self._module_client = None
        self._iot_client_initialized = False
        self._twin_sync_in_progress = False
        self._load_audio_environment_variables()
        self._debug_environment()
    
    def _debug_environment(self) -> None:
        self.logger.info("=== IoT Edge Environment Variables ===")
        edge_vars = [
            "IOTEDGE_DEVICEID",
            "IOTEDGE_MODULEID",
            "IOTEDGE_WORKLOADURI",
            "IOTEDGE_IOTHUBHOSTNAME",
            "IOTEDGE_GATEWAYHOSTNAME",
            "IOTEDGE_APIVERSION",
            "IOTEDGE_MODULEGENERATIONID",
            "IOTEDGE_AUTHSCHEME"
        ]
        
        for var in edge_vars:
            value = os.environ.get(var)
            if value:
                if len(value) > 10 and var not in ["IOTEDGE_DEVICEID", "IOTEDGE_MODULEID"]:
                    display_value = value[:5] + "..." + value[-5:]
                else:
                    display_value = value
                self.logger.info("%s: %s", var, display_value)
            else:
                self.logger.warning("%s: NOT SET", var)
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.logger.info("OPENAI_API_KEY: %s... (configured)", '*' * 10)
        else:
            self.logger.warning("OPENAI_API_KEY: NOT SET")
    
    def _load_audio_environment_variables(self) -> None:
        """Load audio device configuration from environment variables"""
        # Check for audio device environment variables
        capture_device = os.environ.get("CAPTURE_DEVICE")
        playback_device = os.environ.get("PLAYBACK_DEVICE")
        audio_device = os.environ.get("AUDIO_DEVICE")  # Legacy fallback
        
        # Store environment variables in runtime_config for highest priority
        # Only set if explicitly provided via environment
        if capture_device:
            self.runtime_config["audio.mic_device"] = capture_device
            self.logger.info("CAPTURE_DEVICE environment override: %s", capture_device)
        
        if playback_device:
            self.runtime_config["audio.speaker_device"] = playback_device
            self.logger.info("PLAYBACK_DEVICE environment override: %s", playback_device)
        
        # Fallback to AUDIO_DEVICE if specific devices not set
        if audio_device:
            if not capture_device:
                self.runtime_config["audio.mic_device"] = audio_device
                self.logger.info("AUDIO_DEVICE environment override for mic: %s", audio_device)
            if not playback_device:
                self.runtime_config["audio.speaker_device"] = audio_device
                self.logger.info("AUDIO_DEVICE environment override for speaker: %s", audio_device)
    
    def _get_default_config(self) -> Dict[str, Any]:
        defaults_path = os.path.join(os.path.dirname(__file__), 'defaults.json')
        default_config = self.load_from_file(defaults_path)
        
        if not default_config:
            self.logger.error("FATAL: Cannot load required configuration file: %s", defaults_path)
            raise FileNotFoundError(f"Required configuration file not found: {defaults_path}")
        
        self.logger.info("Loaded default configuration from %s with %d top-level keys", defaults_path, len(default_config))
        return default_config
    
    def load_from_file(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            self.logger.warning("Config file not found: %s", file_path)
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info("Loaded config from %s", file_path)
            return config
        except Exception as e:
            self.logger.error("Failed to load config from %s: %s", file_path, e)
            return {}
    
    def _initialize_iot_client(self) -> None:
        warnings.warn(
            "ConfigLoader IoT functionality is deprecated. Use infrastructure.iot.connection_manager.IoTConnectionManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.warning("DEPRECATED: ConfigLoader IoT client initialization. Please migrate to IoTConnectionManager.")
        
        if self._iot_client_initialized:
            return
            
        try:
            from azure.iot.device import IoTHubModuleClient
            self.logger.info("Creating IoT Hub Module Client from edge environment...")
            self._module_client = IoTHubModuleClient.create_from_edge_environment()
            self.logger.info("IoT Hub Module Client created successfully")
            
            try:
                self.logger.info("Attempting to connect to IoT Hub...")
                self._module_client.connect()
                self.logger.info("Successfully connected to IoT Hub")
                self._iot_client_initialized = True
            except Exception as conn_e:
                self.logger.error("Failed to connect to IoT Hub: %s", conn_e)
                self._module_client = None
                
        except Exception as e:
            self.logger.error("Failed to initialize IoT Hub Module Client: %s", e)
            import traceback
            self.logger.error("Traceback: %s", traceback.format_exc())
            self._module_client = None
    
    def sync_with_twin(self) -> None:
        warnings.warn(
            "ConfigLoader.sync_with_twin() is deprecated. Use infrastructure.iot.connection_manager.IoTConnectionManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.warning("DEPRECATED: ConfigLoader.sync_with_twin(). Please migrate to IoTConnectionManager.")
        
        # 1. Prevent concurrent execution
        if self._twin_sync_in_progress:
            self.logger.warning("Twin sync already in progress, skipping")
            return
        
        # 2. Ensure client is initialized
        if not self._iot_client_initialized:
            self._initialize_iot_client()
            
        if not self._module_client:
            self.logger.warning("Module client not available, skipping twin sync")
            return
        
        # 3. Execute with timeout protection
        self._twin_sync_in_progress = True
        try:
            self._execute_twin_sync_safely()
        finally:
            self._twin_sync_in_progress = False
    
    def _execute_twin_sync_safely(self) -> None:
        """Execute twin sync with timeout protection - single, simple implementation"""
        timeout_seconds = 10
        start_time = time.time()
        timeout_flag = threading.Event()
        
        # Simple timeout mechanism
        timeout_timer = threading.Timer(timeout_seconds, timeout_flag.set)
        timeout_timer.start()
        
        try:
            self.logger.info("Starting twin sync with %d-second timeout...", timeout_seconds)
            
            # Check timeout before heavy operation
            if timeout_flag.is_set():
                self.logger.error("Twin sync timed out before execution")
                return
                
            twin = self._module_client.get_twin()
            
            # Check timeout after heavy operation  
            if timeout_flag.is_set():
                self.logger.error("Twin sync timed out during execution")
                return
                
            desired_props = twin.get("desired", {})
            self.config = self._merge_config(self.config, desired_props)
            
            elapsed = time.time() - start_time
            self.logger.info("Twin sync completed successfully (%.2fs)", elapsed)
            
        except Exception as e:
            if not timeout_flag.is_set():
                elapsed = time.time() - start_time
                self.logger.error("Twin sync failed after %.2fs: %s", elapsed, e)
            else:
                self.logger.error("Twin sync failed due to timeout")
        finally:
            timeout_timer.cancel()
    
    def get_config(self) -> Dict[str, Any]:
        return self.config.copy()
    
    def set_runtime(self, key: str, value: Any) -> None:
        """
        Add runtime configuration (device detection results, etc.)
        
        Args:
            key: Configuration key (dot notation supported: "audio.mic_device")
            value: Configuration value
        """
        self.runtime_config[key] = value
        self.logger.debug("Runtime config set: %s = %s", key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value for specific key
        Priority: Runtime Config (includes env vars) > Module Twin > Local Config > Default Config
        
        Args:
            key: Configuration key (dot notation supported: "llm.model")
            default: Default value
            
        Returns:
            Configuration value
        """
        # Highest priority: Runtime configuration (device detection results, etc.)
        if key in self.runtime_config:
            return self.runtime_config[key]
        
        # Existing configuration retrieval logic
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def update(self, updates: Dict[str, Any]) -> None:
        self.config = self._merge_config(self.config, updates)
        self.logger.info("Updated configuration with %d keys", len(updates))
    
    def _merge_config(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        result = base.copy()
        
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @property
    def module_client(self):
        """
        DEPRECATED: Access to module_client property.
        Use infrastructure.iot.connection_manager.IoTConnectionManager instead.
        """
        warnings.warn(
            "ConfigLoader.module_client property is deprecated. Use infrastructure.iot.connection_manager.IoTConnectionManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.logger.warning("DEPRECATED: ConfigLoader.module_client property access. Please migrate to IoTConnectionManager.")
        return self._module_client
