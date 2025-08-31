"""
Voice Conversation Module End-to-End Tests

Tests the complete flow from voice input to response output
in conditions close to the actual environment.
"""
import pytest
import time
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import wave
import numpy as np

from main import Application
from infrastructure.config.config_loader import ConfigLoader


class TestVoiceConversationE2E:
    """Voice conversation module E2E tests"""
    
    @pytest.fixture
    def test_config(self):
        """Test configuration"""
        return {
            "vad": {
                "mode": 3,
                "speech_threshold": 30,
                "silence_threshold": 10,
                "timeout": 10
            },
            "stt": {
                "api_key": os.getenv("OPENAI_API_KEY", "test-key"),
                "model": "whisper-1",
                "language": "ja"
            },
            "llm": {
                "api_key": os.getenv("OPENAI_API_KEY", "test-key"),
                "model": "gpt-4o-mini",
                "temperature": 0.7
            },
            "tts": {
                "api_key": os.getenv("OPENAI_API_KEY", "test-key"),
                "voice": "nova",
                "speed": 1.0
            },
            "memory": {
                "dir": "/tmp/memories"
            },
            "conversation": {
                "system_base_prompt": "You are a conversation partner for the elderly. Please respond concisely and kindly.",
                "token_limit": 4000,
                "immediate_memory_token_limit": 25000,
                "exit_phrases": ["goodbye", "bye bye"],
                "sleep_mode_enabled": True,
                "sleep_threshold": 5,
                "greeting_interval_hours": 6,
                "response_timeout": 30.0
            },
            "module": {
                "iot_hub_connection_string": ""
            }
        }
    
    @pytest.fixture
    def mock_audio_file(self):
        """Generate test audio file"""
        def create_audio(duration=2.0, filename=None):
            if filename is None:
                fd, filename = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
            
            # Create audio data with 16kHz sample rate, mono
            sample_rate = 16000
            t = np.linspace(0, duration, int(sample_rate * duration))
            # 440Hz sine wave (A note)
            audio_data = np.sin(2 * np.pi * 440 * t)
            
            # Convert to 16-bit integer
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # Save as WAV file
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)   # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            return filename
        
        return create_audio
    
    @patch('infrastructure.audio.audio_device.pyaudio.PyAudio')
    @patch('infrastructure.audio.vad_processor.webrtcvad.Vad')
    @patch('infrastructure.ai.whisper_client.openai.OpenAI')
    @patch('infrastructure.ai.openai_client.openai.OpenAI')
    @patch('infrastructure.ai.tts_client.openai.OpenAI')
    def test_single_conversation_turn(
        self, mock_tts_openai, mock_llm_openai, mock_stt_openai,
        mock_vad, mock_pyaudio, test_config, mock_audio_file
    ):
        """Single conversation turn E2E test"""
        # PyAudio mock setup
        mock_audio = Mock()
        mock_pyaudio.return_value = mock_audio
        mock_stream = Mock()
        mock_audio.open.return_value = mock_stream
        mock_stream.read.return_value = b'\x00' * 3200  # Silence data
        
        # VAD mock setup
        mock_vad_instance = Mock()
        mock_vad.return_value = mock_vad_instance
        mock_vad_instance.is_speech.return_value = True
        
        # Prepare audio file
        audio_file = mock_audio_file(duration=2.0)
        
        # Mock Whisper API
        mock_stt_client = Mock()
        mock_stt_openai.return_value = mock_stt_client
        mock_stt_client.audio.transcriptions.create.return_value = Mock(
            text="Hello, nice weather today"
        )
        
        # Mock GPT API
        mock_llm_client = Mock()
        mock_llm_openai.return_value = mock_llm_client
        mock_llm_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Yes, it's really nice weather! Shall we go for a walk?"))]
        )
        
        # Mock TTS API
        mock_tts_client = Mock()
        mock_tts_openai.return_value = mock_tts_client
        mock_response = Mock()
        mock_response.iter_bytes.return_value = [b'fake_audio_data']
        mock_tts_client.audio.speech.create.return_value = mock_response
        
        # Mock ConfigLoader
        with patch('main.ConfigLoader') as MockConfigLoader:
            mock_loader = Mock()
            mock_loader.get.side_effect = lambda key, default=None: {
                "vad.mode": 3,
                "vad.speech_threshold": 30,
                "vad.silence_threshold": 10,
                "stt.api_key": "test-key",
                "stt.model": "whisper-1",
                "stt.language": "ja",
                "llm.api_key": "test-key",
                "llm.model": "gpt-4o-mini",
                "llm.temperature": 0.7,
                "tts.api_key": "test-key",
                "tts.voice": "nova", 
                "tts.speed": 1.0,
                "memory.dir": "/tmp/memories"
            }.get(key, default)
            mock_loader.get_config.return_value = test_config
            mock_loader.load_from_file.return_value = None
            MockConfigLoader.return_value = mock_loader
            
            # Mock VADProcessor's wait_for_speech
            with patch('infrastructure.audio.vad_processor.VADProcessor.wait_for_speech') as mock_wait:
                mock_wait.return_value = audio_file
                
                # Start application
                app = Application()
                with patch('main.signal.signal'):
                    app.setup()
                
                # Execute one conversation turn
                with patch.object(app.voice_service, 'run') as mock_run:
                    # Execute process_conversation once instead of run method
                    app.voice_service.initialize()
                    result = app.voice_service.process_conversation()
                    
                    # Verify
                    assert result is True  # Conversation continues
                    
                    # Verify each API was called
                    mock_stt_client.audio.transcriptions.create.assert_called_once()
                    mock_llm_client.chat.completions.create.assert_called_once()
                    mock_tts_client.audio.speech.create.assert_called_once()
        
        # Cleanup
        os.unlink(audio_file)
    
    @patch('infrastructure.config.config_loader.IoTHubModuleClient')
    def test_module_twin_update_e2e(self, MockIoTClient, test_config):
        """Module Twin update E2E test"""
        # Mock IoT Hub client
        mock_client = Mock()
        mock_client.connect.return_value = None
        MockIoTClient.create_from_connection_string.return_value = mock_client
        
        # Initial Module Twin values
        initial_twin = {
            "desired": test_config,
            "reported": {}
        }
        mock_client.get_twin.return_value = initial_twin
        
        # Test Twin sync with ConfigLoader
        config_loader = ConfigLoader()
        config_loader.sync_with_twin()
        
        # Simulate Twin update
        twin_patch = {
            "conversation": {
                "sleep_threshold": 10,
                "response_timeout": 60.0
            }
        }
        
        # Get and execute Twin update handler
        twin_update_handler = mock_client.on_twin_desired_properties_patch_received
        if twin_update_handler:
            twin_update_handler(twin_patch)
        
        # Verify settings were updated
        updated_config = config_loader.get_config()
        assert updated_config["conversation"]["sleep_threshold"] == 10
        assert updated_config["conversation"]["response_timeout"] == 60.0
    
    def test_memory_persistence_e2e(self, test_config, tmp_path):
        """Memory persistence E2E test"""
        # Create memory directory
        memory_dir = tmp_path / "memories"
        memory_dir.mkdir()
        test_config["memory"]["dir"] = str(memory_dir)
        
        # Create previous day's memory file
        memory_data = {
            "date": "2025-06-30",
            "short_term": [
                {"summary": "Talked about garden flowers with Hanako"}
            ],
            "long_term": [
                {"summary": "Loves flowers, especially growing roses"}
            ]
        }
        
        with open(memory_dir / "memory_20250630.json", 'w') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
        
        # Integration test of ConfigLoader and MemoryRepository
        from infrastructure.memory.memory_repository import MemoryRepository
        
        repo = MemoryRepository(memories_dir=str(memory_dir))
        loaded_memory = repo.get_latest_memory()
        
        assert loaded_memory is not None
        assert loaded_memory["date"] == "2025-06-30"
        assert len(loaded_memory["short_term"]) == 1
        assert "Hanako" in loaded_memory["short_term"][0]["summary"]
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not available"
    )
    def test_real_api_integration(self, test_config):
        """Integration test using actual API (optional)"""
        # This test runs only when actual API key is available
        from infrastructure.ai.llm_client import LLMClient
        from infrastructure.ai.stt_client import STTClient
        from infrastructure.ai.tts_client import TTSClient
        
        # Mock ConfigLoader作成
        from unittest.mock import Mock
        mock_config_loader = Mock()
        mock_config_loader.get.side_effect = lambda key: {
            'llm.model': 'gpt-4o-mini',
            'llm.max_tokens': 500,
            'llm.temperature': 0.7
        }.get(key)
        
        # Create actual client
        llm_client = LLMClient(mock_config_loader)
        
        # Simple test conversation
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]
        
        system_prompt = "You are a helpful assistant."
        response = openai_client.complete_chat(messages, system_prompt)
        assert response is not None
        assert len(response) > 0
        print(f"AI Response: {response}")
    
    def test_graceful_shutdown_e2e(self, test_config):
        """Graceful shutdown E2E test"""
        import signal
        import threading
        import time
        
        # Test flag for signal handler
        shutdown_called = False
        
        def signal_handler(signum, frame):
            nonlocal shutdown_called
            shutdown_called = True
        
        # Save original handler
        original_handler = signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Send SIGTERM from another thread
            def send_signal():
                time.sleep(0.1)
                os.kill(os.getpid(), signal.SIGTERM)
            
            thread = threading.Thread(target=send_signal)
            thread.start()
            
            # Wait for signal to be processed
            thread.join(timeout=1.0)
            time.sleep(0.2)
            
            # Verify signal handler was called
            assert shutdown_called is True
            
        finally:
            # Restore original handler
            signal.signal(signal.SIGTERM, original_handler)