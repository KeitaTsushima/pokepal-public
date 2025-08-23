"""
Azure Speech Text-to-Speech Client - Refactored Facade
High-quality speech synthesis with streaming support (parallel generation + sequential output)
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Iterator

from .tts_core_synthesizer import TTSCoreSynthesizer
from .tts_file_manager import TTSFileManager
import json
import os


class TTSClient:
    """Azure Speech Text-to-Speech Client - Refactored Facade"""
    
    def __init__(self, config_loader):
        """
        Args:
            config_loader: ConfigLoader instance for dynamic configuration access
        
        Environment Variables:
            AZURE_SPEECH_KEY: Azure Speech Service subscription key (required)
        """
        self.logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        defaults_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'defaults.json')
        with open(defaults_path, 'r', encoding='utf-8') as f:
            defaults = json.load(f)
        tts_defaults = defaults.get('tts', {})
        self.config_schema = tts_defaults.get('config_schema', {})
        
        self.core_synthesizer = TTSCoreSynthesizer(config_loader)
        
        self.file_manager = TTSFileManager(self.core_synthesizer.tmp_dir)
        
        self.logger.info("Azure Speech TTS Client initialized")
    
    async def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """
        Async speech synthesis using Azure Speech SDK
        
        Args:
            text: Text to synthesize
            output_file: Optional output file path
            
        Returns:
            Path to generated audio file or None if failed
        """
        if output_file is None:
            output_file = self.file_manager.get_temp_file_path("response")
        
        # Use asyncio.to_thread to run blocking Azure Speech SDK in thread pool
        # This prevents blocking the event loop during TTS processing
        result = await asyncio.to_thread(
            self.core_synthesizer.synthesize_basic, text, output_file
        )
        
        if result:
            cleanup_delay = self.file_manager.calculate_cleanup_delay(text)
            # File cleanup is also blocking, run in thread pool
            await asyncio.to_thread(
                self.file_manager.cleanup_audio_file, result, cleanup_delay
            )
        
        return result    
    
    def update_config(self) -> None:
        self.core_synthesizer.update_config()
        self.logger.info("TTS configuration updated from ConfigLoader")

    def cleanup(self) -> None:
        try:
            self.core_synthesizer.cleanup()
            self.file_manager.cleanup_all_temp_files()            
            self.logger.info("Azure Speech TTS Client cleanup completed")
        except Exception as e:
            self.logger.error("Azure Speech TTS Client cleanup error: %s", e)
    