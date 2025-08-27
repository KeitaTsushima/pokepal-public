#!/usr/bin/env python
"""
Entry point for the voice conversation module

Assembles all components using dependency injection (DI)
and starts the application.
"""
import asyncio
import logging
import os
import sys
import signal
from typing import Optional

from domain.conversation import ConversationConfig

from application.conversation_service import ConversationService
from application.voice_interaction_service import VoiceInteractionService
from application.audio_capture_service import AudioCaptureService
from application.proactive_service import ProactiveService

from adapters.input.iot_commands import IoTCommandAdapter
from adapters.input.signal_handler import SignalHandler
from adapters.output.audio_output import AudioOutputAdapter

from infrastructure.iot.telemetry_client import IoTTelemetryClient
from infrastructure.ai.llm_client import LLMClient
from infrastructure.ai.tts_client import TTSClient
from infrastructure.ai.stt_client import STTClient
from infrastructure.audio.vad_processor import VADProcessor
from infrastructure.audio.audio_device import AudioDevice
from infrastructure.audio.audio_device_detector import AudioDeviceDetector
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.config.twin_sync import TwinSync
from infrastructure.iot.connection_manager import IoTConnectionManager
from infrastructure.memory.memory_repository import MemoryRepository
from infrastructure.ai.async_openai_shared import cleanup_shared_openai, get_shared_openai
from infrastructure.security.async_key_vault import cleanup_async_key_vault, get_async_key_vault

logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Application:
    """Application management class for the entire system"""
    
    def __init__(self):
        self.voice_service: Optional[VoiceInteractionService] = None
        self.proactive_service: Optional[ProactiveService] = None
        self.config_loader: Optional[ConfigLoader] = None
        self.signal_handler: Optional[SignalHandler] = None
        self.twin_sync: Optional[TwinSync] = None
        self.memory_repository: Optional[MemoryRepository] = None


    # TODO: Split this method later
    """
        def setup(self):
        logger.info("Setting up...")
        self._load_config()
        self._build_infrastructure()
        self._build_adapters()
        self._build_application_services()
        self._setup_signal_handlers()
        logger.info("Setup complete")
    """
    def setup(self) -> None:
        logger.info("Setting up application components...")
        
        # 1. Load configuration
        self.config_loader = ConfigLoader()
        
        # Load local configuration before IoT Hub connection
        local_config = self.config_loader.load_from_file("/app/config/config.json")
        if local_config:
            self.config_loader.update(local_config)
        
        # NOTE: Removed deprecated sync_with_twin() call here to avoid duplicate IoT client creation
        # Twin sync is now handled via IoTConnectionManager and TwinSync below
        
        # 2. Build Infrastructure layer
        # Perform dynamic detection only if not already set by environment variables
        if "audio.mic_device" not in self.config_loader.runtime_config or "audio.speaker_device" not in self.config_loader.runtime_config:
            audio_detector = AudioDeviceDetector()
            detected_devices = audio_detector.detect_devices()  # Guaranteed to return valid values
            
            # Set detected devices only if not already set by env vars
            if "audio.mic_device" not in self.config_loader.runtime_config:
                self.config_loader.set_runtime("audio.mic_device", detected_devices["mic"])
                logger.info("Auto-detected mic device: %s", detected_devices["mic"])
            
            if "audio.speaker_device" not in self.config_loader.runtime_config:
                self.config_loader.set_runtime("audio.speaker_device", detected_devices["speaker"])
                logger.info("Auto-detected speaker device: %s", detected_devices["speaker"])
        
        audio_device = AudioDevice(self.config_loader)

        # TODO: Consider introducing DI Container - automate manual dependency injection
        # Currently manually assembling 12 services, but introducing DI Container libraries
        # like dependency-injector or punq could significantly simplify main.py and improve testability
        
        vad_processor = VADProcessor(
            sample_rate=self.config_loader.get("audio.sample_rate"),
            vad_mode=self.config_loader.get("vad.mode")
        )
        
        audio_capture_service = AudioCaptureService(
            vad_processor=vad_processor,
            config_loader=self.config_loader
        )
        
        stt_client = STTClient(self.config_loader)
        
        llm_client = LLMClient(self.config_loader)
        
        tts_client = TTSClient(self.config_loader)
        
        self.memory_repository = MemoryRepository(
            memory_dir=self.config_loader.get("memory.dir")
        )
        
        # Initialize IoT Connection Manager (single IoT Hub client instance)
        iot_connection_manager = IoTConnectionManager()
        iot_connection_manager.connect()
        
        # Sync configuration with Module Twin via IoTConnectionManager
        try:
            twin = iot_connection_manager.get_client().get_twin()
            if twin and "desired" in twin:
                desired_props = twin["desired"]
                # Apply twin properties to config (excluding system properties)
                for key, value in desired_props.items():
                    if not key.startswith("$"):
                        self.config_loader.update({key: value})
                logger.info("Configuration synced with Module Twin")
        except Exception as e:
            logger.warning(f"Failed to sync with module twin, continuing with local config: {e}")
        
        # Initialize Twin sync (to receive memory updates)
        self.twin_sync = TwinSync(self.config_loader, self.memory_repository, iot_connection_manager)
        
        # 3. Build Adapters layer
        text_to_speech = AudioOutputAdapter(
            tts_client=tts_client,
            audio_device=audio_device,
            config_loader=self.config_loader
        )
        
        telemetry_sender = IoTTelemetryClient(
            iot_client=iot_connection_manager.get_client(),
            config_loader=self.config_loader
        )
        
        # 4. Create Domain configuration
        conversation_config = ConversationConfig(self.config_loader)
        
        # 5. Build Application layer
        conversation_service = ConversationService(
            config=conversation_config,
            ai_client=llm_client,
            memory_repository=self.memory_repository,
            telemetry_adapter=telemetry_sender,
            clause_break_threshold=self.config_loader.get('tts.streaming.clause_break_threshold')
        )
        
        self.voice_service = VoiceInteractionService(
            conversation_service=conversation_service,
            audio_capture=audio_capture_service,
            speech_to_text=stt_client,
            audio_output=text_to_speech,
            no_voice_sleep_threshold=self.config_loader.get("conversation.no_voice_sleep_threshold")
        )
        
        self.proactive_service = ProactiveService(
            audio_output=text_to_speech,
            config_loader=self.config_loader
        )
        
        # Set ConversationService for TwinSync
        # TODO: Review TwinSync initialization order
        # Current: Create TwinSync first, then set conversation_service later
        # Ideal: Initialize TwinSync after ConversationService creation
        # Note: Confirm dependency relationships before fixing initialization order
        """
        Issues:
        Incomplete initialization:
        conversation_service doesn't exist when TwinSync is created
        Risk of forgetting to set it later
        Unclear dependencies:
        Dependencies are not apparent from just looking at the constructor
        """
        
        self.proactive_service.set_conversation_service(conversation_service)
        
        # Initialize IoTCommandAdapter (when services are ready)
        iot_commands = IoTCommandAdapter(
            self.config_loader,
            services={
                'conversation_service': conversation_service,
                'memory_manager': self.memory_repository
            },
            iot_client=iot_connection_manager.get_client()
        )
        
        iot_commands.register_update_callback('memory_update', 
            lambda update: self.twin_sync.receive_memory_summary(update))
        
        iot_commands.register_update_callback('conversation_restore',
            lambda recovery_data: conversation_service.recover_conversations(recovery_data))
        
        # 6. Setup signal handlers
        self.signal_handler = SignalHandler()
        self.signal_handler.register(signal.SIGTERM, lambda signum: self.stop())
        self.signal_handler.register(signal.SIGINT, lambda signum: self.stop())
        self.signal_handler.setup()
        
        logger.info("Application setup completed")
    
    async def run(self) -> None:
        if not self.voice_service:
            raise RuntimeError("Application not properly setup")
        
        try:
            logger.info("Starting voice conversation module...")
            
            self.twin_sync.report_startup()
            
            # Key Vault warmup (AAD authentication pre-establishment)
            # Temporarily disabled for debugging
            # await self._warmup_key_vault()
            
            # STT warmup to eliminate 3.5s delay on first conversation
            if hasattr(self.voice_service, 'speech_to_text') and hasattr(self.voice_service.speech_to_text, '_lazy_warmup'):
                logger.info("Starting STT warmup at startup...")
                try:
                    await self.voice_service.speech_to_text._lazy_warmup()
                except Exception as e:
                    logger.warning(f"STT warmup failed at startup: {e}")
            
            # LLM and SharedAsyncOpenAI warmup to eliminate 5s delay on first conversation
            logger.info("Starting LLM warmup at startup...")
            try:
                # Initialize SharedAsyncOpenAI and HTTP client
                shared_openai = await get_shared_openai()
                
                # Pre-fetch LLM client (includes Key Vault access and caching)
                openai_secret_name = os.environ.get('OPENAI_SECRET_NAME')
                if openai_secret_name:
                    await shared_openai.get_llm_client(openai_secret_name)
                    logger.info("LLM client pre-initialized and cached successfully")
                else:
                    logger.warning("OPENAI_SECRET_NAME not found, skipping LLM warmup")
                    
            except Exception as e:
                logger.warning(f"LLM warmup failed at startup: {e}")
            
            # Pre-load memory file to eliminate disk I/O on first conversation
            if self.memory_repository:
                try:
                    self.memory_repository.preload_memory()
                    logger.info("Memory file pre-loaded for fast access")
                except Exception as e:
                    logger.warning(f"Memory preload failed: {e}")
            
            await self.voice_service.initialize()
            
            if self.proactive_service:
                try:
                    logger.info("Starting ProactiveService...")
                    self.proactive_service.start()
                    logger.info("ProactiveService started successfully")
                except Exception as e:
                    logger.error(f"Failed to start ProactiveService: {e}", exc_info=True)
                    # Continue with other functions even if ProactiveService startup fails
            else:
                logger.warning("ProactiveService is None, skipping start")
            
            await self.voice_service.run()
            
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        logger.info("Stopping application...")
        
        if self.proactive_service:
            try:
                self.proactive_service.stop()
                logger.info("ProactiveService stopped")
            except Exception as e:
                logger.error(f"proactive_service.stop() raised during shutdown: {e}")
        
        if self.voice_service:
            try:
                self.voice_service.stop()
            except Exception as e:
                logger.error(f"voice_service.stop() raised during shutdown: {e}")

        # Async resource cleanup (implemented for OpenAI client)
        # TODO: Add remaining cleanup processes:
        # - Close IoT Hub connection (azure_iot_device.IoTHubModuleClient)
        # - Audio device resources (microphone/speaker)
        # - Domain layer resources via conversation.end_conversation() (tiktoken, Deque, etc.)
        # - Temporary file cleanup
        
        if self.signal_handler:
            try:
                self.signal_handler.restore()
            except Exception as e:
                logger.error(f"signal_handler.restore() raised during shutdown: {e}")
        
        logger.info("Application stopped")
    
    async def _warmup_key_vault(self) -> None:
        """Warm up Key Vault AAD authentication (best-effort)"""
        try:
            timeout_sec = float(os.getenv("KV_WARMUP_TIMEOUT_SEC", "5.0"))
            kv_client = await get_async_key_vault()
            success = await kv_client.warmup_token_only(timeout_sec)
            
            if success:
                logger.info("Key Vault warmup completed successfully")
            else:
                logger.info("Key Vault warmup failed (continuing anyway)")
                
        except Exception as e:
            logger.warning(f"Key Vault warmup error (best-effort, continuing): {e}")

async def main():
    app = Application()
    
    try:
        app.setup()
        await app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure async resources are cleaned up on any exit
        try:
            await cleanup_shared_openai()
            await cleanup_async_key_vault()
            logger.info("Async resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Failed to cleanup async resources: {e}")

if __name__ == "__main__":
    asyncio.run(main())
