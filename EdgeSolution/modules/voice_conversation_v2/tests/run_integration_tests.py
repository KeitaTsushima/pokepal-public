#!/usr/bin/env python
"""
Integration test execution script

Executes integration tests with properly mocked openai module.
"""
import sys
import os
import subprocess
from unittest.mock import MagicMock

# Add project root directory to PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create mock for openai module
mock_openai = MagicMock()
mock_openai.OpenAI = MagicMock
mock_openai.AsyncOpenAI = MagicMock
sys.modules['openai'] = mock_openai

# Mock webrtcvad module
mock_webrtcvad = MagicMock()
mock_webrtcvad.Vad = MagicMock
sys.modules['webrtcvad'] = mock_webrtcvad

# Mock pyaudio module
mock_pyaudio = MagicMock()
mock_pyaudio.PyAudio = MagicMock
mock_pyaudio.paInt16 = 2
sys.modules['pyaudio'] = mock_pyaudio

# Mock whisper module
mock_whisper = MagicMock()
sys.modules['whisper'] = mock_whisper

# Mock azure.iot.device module
mock_azure = MagicMock()
mock_azure.iot = MagicMock()
mock_azure.iot.device = MagicMock()
mock_azure.iot.device.IoTHubModuleClient = MagicMock
mock_azure.iot.device.Message = MagicMock
mock_azure.iot.device.MethodResponse = MagicMock
sys.modules['azure'] = mock_azure
sys.modules['azure.iot'] = mock_azure.iot
sys.modules['azure.iot.device'] = mock_azure.iot.device

# Mock tiktoken module
mock_tiktoken = MagicMock()
mock_tiktoken.encoding_for_model = MagicMock()
mock_tiktoken.get_encoding = MagicMock()
sys.modules['tiktoken'] = mock_tiktoken

# Execute tests
if __name__ == "__main__":
    # Execute integration tests only
    test_path = "tests/integration"
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
    
    cmd = [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"]
    
    # Set environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    # Execute tests
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)