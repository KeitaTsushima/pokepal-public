"""
Audio Device Auto-Detection
Automatically detects available audio input/output devices on the system
"""
import subprocess
import re
import logging
from typing import Dict, List, Optional, Tuple


class AudioDeviceDetector:
    """Audio device auto-detection utility class"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Default fallback devices (configurable via environment)
        self.default_speaker = "plughw:0,0"
        self.default_mic = "plughw:0,0"
    
    def detect_devices(self) -> Dict[str, str]:
        """
        Detect available audio devices with guaranteed valid return values
        
        Returns:
            Dict containing detected device info {"speaker": "plughw:X,0", "mic": "plughw:Y,0"}
            Always returns valid device names (never None or empty strings)
        """
        try:
            playback_devices = self._get_playback_devices()
            capture_devices = self._get_capture_devices()
            
            result = {
                "speaker": self._select_speaker_device(playback_devices),
                "mic": self._select_microphone_device(capture_devices)
            }
            
            self._log_detection_summary(playback_devices, capture_devices)
            self._validate_result(result)
            
            return result
            
        except Exception as e:
            return self._handle_detection_error(e)
    
    def _get_playback_devices(self) -> List[Tuple[int, str]]:
        try:
            output = subprocess.check_output(['aplay', '-l'], text=True)
            return self._parse_device_list(output)
        except Exception as e:
            self.logger.error("Failed to retrieve playback devices: %s", e)
            return []
    
    def _get_capture_devices(self) -> List[Tuple[int, str]]:
        try:
            output = subprocess.check_output(['arecord', '-l'], text=True)
            return self._parse_device_list(output)
        except Exception as e:
            self.logger.error("Failed to retrieve capture devices: %s", e)
            return []
    
    def _parse_device_list(self, output: str) -> List[Tuple[int, str]]:
        """
        Parse aplay/arecord output with internationalization support
        
        Args:
            output: Command output from aplay -l or arecord -l
            
        Returns:
            List of (card_number, device_name) tuples
        """
        devices = []
        try:
            # Support both English and Japanese output formats
            # English: "Card X: DeviceName [Description]"  
            # Japanese: "カード X: DeviceName [Description]"
            pattern = r'(?:カード|[Cc]ard)\s+(\d+):\s+([^[]+)\s*\['
            
            for match in re.finditer(pattern, output):
                try:
                    card_num = int(match.group(1))
                    device_name = match.group(2).strip()
                    devices.append((card_num, device_name))
                except (ValueError, AttributeError) as e:
                    self.logger.warning("Failed to parse device info: %s - %s", match.group(0), e)
                    continue
        except Exception as e:
            self.logger.error("Failed to process device list with regex: %s", e)
        
        self.logger.debug("Parse result: detected %d devices", len(devices))
        return devices
    
    def _select_speaker_device(self, playback_devices: List[Tuple[int, str]]) -> str:
        for card, name in playback_devices:
            # Check for USB devices (including USB Audio Class devices)
            if "USB" in name.upper() or "UAC" in name.upper():
                device = f"plughw:{card},0"
                self.logger.info("Speaker device detected: %s (%s)", name, device)
                return device
        
        if playback_devices:
            card, name = playback_devices[0]
            device = f"plughw:{card},0"
            self.logger.info("Speaker device detected: %s (%s)", name, device)
            return device
        
        return self.default_speaker
    
    def _select_microphone_device(self, capture_devices: List[Tuple[int, str]]) -> str:
        for card, name in capture_devices:
            if "USB" in name.upper() and "PNP" in name.upper():
                device = f"plughw:{card},0"
                self.logger.info("Microphone device detected: %s (%s)", name, device)
                return device
        
        for card, name in capture_devices:
            if "USB" in name.upper():
                device = f"plughw:{card},0"
                self.logger.info("Microphone device detected: %s (%s)", name, device)
                return device
        
        if capture_devices:
            card, name = capture_devices[0]
            device = f"plughw:{card},0"
            self.logger.info("Microphone device detected: %s (%s)", name, device)
            return device
        
        return self.default_mic
    
    def _log_detection_summary(self, playback_devices: List[Tuple[int, str]], 
                              capture_devices: List[Tuple[int, str]]) -> None:
        if playback_devices or capture_devices:
            self.logger.info("Audio device detection completed: %d speakers, %d microphones", 
                           len(playback_devices), len(capture_devices))
        else:
            self.logger.warning("No audio devices detected. Using default values.")
    
    def _validate_result(self, result: Dict[str, str]) -> None:
        assert result["mic"] is not None and result["mic"] != "", "Mic device must be valid"
        assert result["speaker"] is not None and result["speaker"] != "", "Speaker device must be valid"
    
    def _handle_detection_error(self, error: Exception) -> Dict[str, str]:
        self.logger.error("Unexpected error during audio device detection: %s", error)
        self.logger.warning("Using default audio devices (%s). Dynamic re-detection will occur if device status changes (e.g., USB reconnection).", 
                          self.default_speaker)
        # TODO: Implement dynamic audio device re-detection feature
        # Re-call this method from AudioCaptureService on AudioDeviceError (USB reconnection)
        # Implementation: AudioCaptureService._retry_with_redetection() -> AudioDeviceDetector.detect_devices()
        
        fallback_result = {
            "speaker": self.default_speaker,
            "mic": self.default_mic
        }
        self._validate_result(fallback_result)
        return fallback_result
