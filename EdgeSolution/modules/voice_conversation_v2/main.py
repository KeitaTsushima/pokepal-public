#!/usr/bin/env python
"""
Entry point for the voice conversation module

Assembles all components using dependency injection (DI)
and starts the application.
"""
import logging
import os
import sys
import signal
from typing import Optional

from application.conversation_service import ConversationService
from application.voice_interaction_service import VoiceInteractionService
from application.audio_capture_service import AudioCaptureService
from application.proactive_service import ProactiveService

from adapters.input.iot_commands import IoTCommandAdapter
from adapters.input.signal_handler import SignalHandler
from adapters.output.audio_output import AudioOutputAdapter
from adapters.output.iot_telemetry import IoTTelemetryAdapter

from infrastructure.ai.openai_client import OpenAIClient
from infrastructure.ai.tts_client import TTSClient
from infrastructure.ai.speech_to_text_factory import SpeechToTextFactory
from infrastructure.audio.vad_processor import VADProcessor
from infrastructure.audio.audio_device import AudioDevice
from infrastructure.audio.audio_device_detector import AudioDeviceDetector
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.config.config_factory import ConfigFactory
from infrastructure.config.twin_sync import TwinSync
from infrastructure.memory.memory_repository import MemoryRepository

logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Application:
    """Application management class for the entire system"""
    
    # Required configuration keys
    REQUIRED_CONFIG_KEYS = ["llm.api_key"]
    
    def __init__(self):
        self.voice_service: Optional[VoiceInteractionService] = None
        self.proactive_service: Optional[ProactiveService] = None
        self.config_loader: Optional[ConfigLoader] = None
        self.signal_handler: Optional[SignalHandler] = None
        self.twin_sync: Optional[TwinSync] = None


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
            
        self._validate_required_configs()
        
        try:
            self.config_loader.sync_with_twin()
            # TODO: Fundamental refactoring of initialization order needed
            # Current: temporary solution to reset handlers after module_client initialization
            # Ideal: phased initialization (basic config → IoT connection → Infrastructure → Adapters → Application)
            # Details in "docs/daily-logs/2025-07-17.md"
            # IoTCommandAdapter is initialized in setup(), so skip here
            pass
        except Exception as e:
            logger.warning(f"Failed to sync with module twin, continuing with local config: {e}")
        
        # 2. Build Infrastructure layer
        try:
            detected_devices = AudioDeviceDetector.detect_devices()
        except Exception as e:
            logger.warning(f"Audio device auto-detection failed, falling back to defaults: {e}")
            detected_devices = {"mic": None, "speaker": None}

        # TODO: Create defaults.json to consolidate default values
        # Current: self.config_loader.get("audio.volume", 1.0)
        # Future: self.config_loader.get("audio.volume")  # defaults from defaults.json
            # Implementation plan:
            # 1. Create infrastructure/config/defaults.json ✅ completed
            # 2. Load defaults.json in ConfigLoader constructor
            # 3. Search order in get() method: defaults → runtime → config.json → IoT Twin
            # 4. Remove default value responsibility from main.py (remove hardcoded 16000, 1.0, 5, etc.)
            # 5. Inject dynamic values (detected_devices) via set_runtime_defaults()

        # Get common settings first for efficiency
        mic_device_name = self.config_loader.get("audio.mic_device", detected_devices["mic"])
        sample_rate = self.config_loader.get("audio.sample_rate", 16000)
        
        audio_device = AudioDevice(config={
            'speaker_device': self.config_loader.get("audio.speaker_device", detected_devices["speaker"]),
            'mic_device': mic_device_name,
            'volume': self.config_loader.get("audio.volume", 1.0),
            'sample_rate': sample_rate
        })

        # TODO: Consider introducing DI Container - automate manual dependency injection
        # Currently manually assembling 12 services, but introducing DI Container libraries
        # like dependency-injector or punq could significantly simplify main.py and improve testability
        
        vad_processor = VADProcessor(
            sample_rate=sample_rate,
            vad_mode=self.config_loader.get("vad.mode", 3)
        )
        
        audio_capture_service = AudioCaptureService(
            vad_processor=vad_processor,
            config_loader=self.config_loader
        )
        
        stt_config = {
            'strategy': self.config_loader.get("stt.strategy", "auto"),
            'api_key': self.config_loader.get("llm.api_key"),
            'openai': {
                'model': self.config_loader.get("stt.openai.model", "whisper-1"),
                'language': self.config_loader.get("stt.language", "ja")
            },
            'local': {
                'model_name': self.config_loader.get("stt.model_name", "base"),
                'language': self.config_loader.get("stt.language", "ja")
            }
        }
        speech_to_text_client = SpeechToTextFactory.create(stt_config)
        
        openai_client = OpenAIClient(config={
            'model': self.config_loader.get("llm.model", "gpt-4o-mini"),
            'temperature': self.config_loader.get("llm.temperature", 0.7)
        })
        
        tts_client = TTSClient(config={
            'region': self.config_loader.get("tts.region", "japaneast"),
            'voice_name': self.config_loader.get("tts.voice_name", "ja-JP-NanamiNeural"),
            'speech_rate': self.config_loader.get("tts.speech_rate", 1.0),
            'speech_pitch': self.config_loader.get("tts.speech_pitch", 0)
        })
        
        memory_repository = MemoryRepository(
            memory_dir=self.config_loader.get("memory.dir", "/app/memories")
        )
        
        # Initialize Twin sync (to receive memory updates)
        self.twin_sync = TwinSync(self.config_loader, memory_repository)
        
        # 3. Build Adapters layer
        text_to_speech = AudioOutputAdapter(
            tts_client=tts_client,
            audio_device=audio_device
        )
        
        telemetry_sender = IoTTelemetryAdapter(
            iot_client=self.config_loader.module_client
        )
        
        # 4. Create Domain configuration
        config_factory = ConfigFactory()
        conversation_config = config_factory.create_conversation_config(
            self.config_loader.get_config()
        )
        
        # 5. Build Application layer
        conversation_service = ConversationService(
            config=conversation_config,
            ai_client=openai_client,
            memory_repository=memory_repository,
            telemetry_adapter=telemetry_sender
        )
        
        self.voice_service = VoiceInteractionService(
            conversation_service=conversation_service,
            audio_capture=audio_capture_service,
            speech_to_text=speech_to_text_client,
            audio_output=text_to_speech,
            # TODO: Create defaults.json to consolidate default values
            # Ideal: self.config_loader.get("conversation.no_voice_sleep_threshold")
            no_voice_sleep_threshold=self.config_loader.get("no_voice_sleep_threshold", 5)
        )
        
        self.proactive_service = ProactiveService(
            audio_output=text_to_speech,
            config=self.config_loader.get_config()
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
        self.twin_sync.conversation_service = conversation_service
        
        self.proactive_service.set_conversation_service(conversation_service)
        
        # Initialize IoTCommandAdapter (when services are ready)
        iot_commands = IoTCommandAdapter(
            self.config_loader,
            services={
                'conversation_service': conversation_service,
                'memory_manager': memory_repository
            }
        )
        
        iot_commands.register_update_callback('memory_update', 
            lambda update: self.twin_sync.handle_twin_update({'memory_update': update}))
        
        iot_commands.register_update_callback('conversation_restore',
            lambda recovery_data: conversation_service.recover_conversations(recovery_data))
        
        # 6. Setup signal handlers
        self.signal_handler = SignalHandler()
        self.signal_handler.register(signal.SIGTERM, lambda signum: self.stop())
        self.signal_handler.register(signal.SIGINT, lambda signum: self.stop())
        self.signal_handler.setup()
        
        logger.info("Application setup completed")
    
    def run(self) -> None:
        if not self.voice_service:
            raise RuntimeError("Application not properly setup")
        
        try:
            logger.info("Starting voice conversation module...")
            
            self.twin_sync.report_startup()
            
            self.voice_service.initialize()
            
            if self.proactive_service:
                try:
                    logger.info("Starting ProactiveService...")
                    self.proactive_service.start()
                    logger.info("ProactiveService started successfully")
                except Exception as e:
                    logger.error(f"Failed to start ProactiveService: {e}", exc_info=True)
                    # ProactiveServiceが起動しなくても他の機能は続行
            else:
                logger.warning("ProactiveService is None, skipping start")
            
            self.voice_service.run()
            
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

        # TODO: Add proper resource cleanup (memory optimization for long-running IoT)
        # Required cleanup processes:
        # - Close IoT Hub connection (azure_iot_device.IoTHubModuleClient)
        # - Close OpenAI HTTP client connections
        # - Audio device resources (microphone/speaker)
        # - Domain layer resources via conversation.end_conversation() (tiktoken, Deque, etc.)
        # - Temporary file cleanup
        # Implementation order: Add cleanup() methods to each layer → integrated stop() implementation
        
        if self.signal_handler:
            try:
                self.signal_handler.restore()
            except Exception as e:
                logger.error(f"signal_handler.restore() raised during shutdown: {e}")
        
        logger.info("Application stopped")
    
    def _validate_required_configs(self) -> None:
        missing = [key for key in self.REQUIRED_CONFIG_KEYS if not self.config_loader.get(key)]
        if missing:
            raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")

def main():
    app = Application()
    
    try:
        app.setup()
        app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

