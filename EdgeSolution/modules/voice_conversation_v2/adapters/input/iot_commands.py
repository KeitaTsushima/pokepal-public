"""
IoT Hub Command Processing Adapter

Receives commands from Module Twin and Direct Method,
and routes them to appropriate handlers.

TODO: IoT Commands Quality Improvements (Medium Priority)
1. Improve DI dependency injection pattern (add Protocol definitions)
2. Enhance error handling robustness (retry mechanisms)
3. Consider asynchronous command processing
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional, Tuple
from azure.iot.device import MethodResponse

logger = logging.getLogger(__name__)


class IoTCommandAdapter:
    """Adapter for processing commands from IoT Hub"""

    def __init__(self, config_loader, services: Optional[Dict[str, Any]] = None):
        """
        Args:
            config_loader: Configuration management object
            services: References to application services (optional)
        """
        self.config_loader = config_loader
        self.update_callbacks: Dict[str, Callable] = {}
        self.services = services or {}
        self.start_time = datetime.utcnow()

        self.method_handlers = {
            "update_config": self._handle_update_config,
            "get_status": self._handle_get_status,
            "get_memory_status": self._handle_get_memory_status,
            "get_conversation_history": self._handle_get_conversation_history
        }

        # Use ConfigLoader's module_client (avoid duplicate creation)
        self._setup_handlers()
        logger.info("IoT command adapter initialized with shared IoT Hub connection")

    def _setup_handlers(self) -> None:
        if not self.config_loader.module_client:
            logger.warning("Module client not available yet, handlers will be set up later")
            return

        self.config_loader.module_client.on_twin_desired_properties_patch_received = self._handle_twin_update
        logger.info("Registered Twin update handler")

        self.config_loader.module_client.on_method_request_received = self._on_method_request
        logger.info("Registered Direct Method handler")

    def register_update_callback(self, key: str, callback: Callable) -> None:
        """
        Register update callback for specific configuration key

        Args:
            key: Configuration key (e.g., "scheduler", "health_check")
            callback: Callback function called on update
        """
        self.update_callbacks[key] = callback
        logger.info(f"Registered update callback for key: {key}")

    def _handle_twin_update(self, twin_patch: Dict[str, Any]) -> None:
        try:
            logger.info(f"Received twin update: {json.dumps(twin_patch, indent=2)}")

            special_keys = self._handle_special_updates(twin_patch)
            self._handle_normal_updates(twin_patch, exclude_keys=special_keys)

        except Exception as e:
            logger.error(f"Error handling twin update: {e}")

    def _handle_special_updates(self, twin_patch: Dict[str, Any]) -> set:
        special_keys = set()

        if "conversation_restore" in twin_patch:
            self._process_conversation_restore(twin_patch["conversation_restore"])
            special_keys.add("conversation_restore")

        return special_keys

    def _process_conversation_restore(self, restore_data: Any) -> None:
        logger.info("Detected conversation_restore in twin update")

        if "conversation_restore" not in self.update_callbacks:
            logger.warning("No callback registered for conversation_restore")
            return

        try:
            self.update_callbacks["conversation_restore"](restore_data)
            logger.info("Conversation data restored successfully")

            self._request_twin_cleanup()
            logger.info("Conversation restore process completed")
        except Exception as e:
            logger.error(f"Error in conversation_restore process: {e}")

    def _handle_normal_updates(self, twin_patch: Dict[str, Any], exclude_keys: set) -> None:
        normal_updates = {k: v for k, v in twin_patch.items() if k not in exclude_keys}

        if normal_updates:
            self.config_loader.update(normal_updates)
            logger.debug(f"Updated config: {list(normal_updates.keys())}")

        for key, callback in self.update_callbacks.items():
            if key in normal_updates:
                try:
                    callback(normal_updates[key])
                    logger.info(f"Executed callback for key: {key}")
                except Exception as e:
                    logger.error(f"Error in callback for {key}: {e}")

    def _on_method_request(self, method_request) -> None:
        try:
            logger.info(f"Received method request: {method_request.name}")
            result = self._handle_method_request(method_request)
            self._send_method_response(method_request, result)

        except Exception as e:
            logger.error(f"Error handling method request: {e}")
            self._send_method_response(method_request, (500, {"error": str(e)}))

    def _handle_method_request(self, method_request) -> Tuple[int, Dict[str, Any]]:
        """
        Returns:
            Tuple of (status_code, response_payload)
        """
        method_name = method_request.name
        payload = method_request.payload

        handler = self.method_handlers.get(method_name)
        if handler:
            return handler(payload)
        else:
            logger.warning(f"Unknown method: {method_name}")
            return (404, {"error": "Method not found"})

    def _handle_update_config(self, payload) -> Tuple[int, Dict[str, Any]]:
        try:
            config_updates = json.loads(payload) if payload else {}
            self.config_loader.update(config_updates)
            logger.info(f"Configuration updated: {config_updates}")
            return (200, {"message": "Configuration updated"})
        except json.JSONDecodeError as e:
            return (400, {"error": f"Invalid JSON payload: {e}"})
        except Exception as e:
            return (500, {"error": str(e)})

    def _handle_get_status(self, payload) -> Tuple[int, Dict[str, Any]]:
        try:
            uptime = datetime.utcnow() - self.start_time

            connections = {}
            connections["iot_hub"] = self.config_loader.module_client is not None
            for service_name, service in self.services.items():
                connections[service_name] = service is not None

            status = {
                "status": "running",
                "config": self.config_loader.get_config(),
                "connections": connections,
                "uptime_seconds": int(uptime.total_seconds())
            }
            return (200, status)

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return (200, {
                "status": "error", 
                "error": str(e),
                "config": None
            })

    def _handle_get_memory_status(self, payload) -> Tuple[int, Dict[str, Any]]:
        try:
            memory_mgr = self.services.get('memory_manager')
            if not memory_mgr:
                return (200, {"status": "error", "message": "Memory manager not available"})

            memories = memory_mgr.get_current_memory()
            memory_count = len(memories.get("memories", [])) if memories else 0

            return (200, {
                "status": "ok",
                "memory_count": memory_count,
                "has_character": bool(memories.get("character") if memories else False)
            })
        except Exception as e:
            logger.error(f"Error getting memory status: {e}")
            return (500, {"status": "error", "message": str(e)})

    def _handle_get_conversation_history(self, payload) -> Tuple[int, Dict[str, Any]]:
        try:
            conv_service = self.services.get('conversation_service')
            if not conv_service or not hasattr(conv_service, 'conversation'):
                return (200, {"status": "error", "message": "Conversation service not available"})

            conversation = conv_service.conversation
            if not hasattr(conversation, 'message_manager'):
                return (200, {"status": "error", "message": "Conversation domain object has no messages"})

            conversations = []
            for msg in list(conversation.message_manager.messages)[-10:]:
                conversations.append({
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp),
                    "role": msg.role.value if hasattr(msg.role, 'value') else str(msg.role),
                    "content": msg.content
                })

            return (200, {
                "status": "ok",
                "conversation_count": len(conversations),
                "conversations": conversations
            })
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return (500, {"status": "error", "message": str(e)})

    def _send_method_response(self, method_request, result: Tuple[int, Dict[str, Any]]) -> None:
        if not self.config_loader.module_client:
            logger.warning("Module client not available for method response")
            return

        try:
            status_code, payload = result
            response = MethodResponse(
                request_id=method_request.request_id,
                status=status_code,
                payload=json.dumps(payload)
            )

            self.config_loader.module_client.send_method_response(response)
            logger.info(f"Sent method response: {status_code}")

        except Exception as e:
            logger.error(f"Error sending method response: {e}")

    def _request_twin_cleanup(self) -> None:
        try:
            if not self.config_loader.module_client:
                logger.warning("Module client not available for twin cleanup")
                return

            reported_patch = {
                "conversation_restore_processed": {
                    "timestamp": datetime.now().isoformat(),
                    "status": "completed"
                }
            }

            self.config_loader.module_client.patch_twin_reported_properties(reported_patch)
            logger.info("Reported conversation restore completion")

        except Exception as e:
            logger.error(f"Error requesting twin cleanup: {e}")
