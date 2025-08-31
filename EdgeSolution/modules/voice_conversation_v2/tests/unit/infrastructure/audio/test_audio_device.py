"""
Unit tests for AudioDevice
Tests audio device management implementation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from infrastructure.audio.audio_device import AudioDevice


class TestAudioDevice:
    """Test class for AudioDevice"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        return {
            "speaker_device": "plughw:2,0",
            "mic_device": "plughw:3,0",
            "volume": 1.0,
            "sample_rate": 16000
        }
    
    @pytest.fixture
    def device(self, mock_config):
        """Device under test"""
        return AudioDevice(mock_config)
    
    def test_init(self, device):
        """Test initialization"""
        assert device.speaker_device == "plughw:2,0"
        assert device.mic_device == "plughw:3,0"
        assert device.volume == 1.0
        assert device.sample_rate == 16000
        assert device.speaker_alternatives == [
            'plughw:2,0',
            'hw:2,0',
            'default',
            'plughw:0,0'
        ]
    
    @patch('subprocess.run')
    def test_play_success(self, mock_run, device):
        """Test successful playback"""
        # Setup
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Execute
        result = device.play("/tmp/audio.wav")
        
        # Verify
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ['aplay', '-D', 'plughw:2,0', '/tmp/audio.wav']
    
    @patch('subprocess.run')
    def test_play_with_volume_adjustment(self, mock_run, device):
        """Test playback with volume adjustment"""
        # Setup
        device.volume = 0.5
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Execute
        result = device.play("/tmp/audio.wav")
        
        # Verify
        assert result is True
        # Called twice for sox and aplay
        assert mock_run.call_count == 2
        
        # Verify sox call
        sox_call = mock_run.call_args_list[0][0][0]
        assert sox_call[0] == 'sox'
        assert 'vol' in sox_call
        assert '0.5' in sox_call
        
        # Verify aplay call
        aplay_call = mock_run.call_args_list[1][0][0]
        assert aplay_call[0] == 'aplay'
        assert '_adjusted.wav' in aplay_call[-1]
    
    @patch('subprocess.run')
    def test_play_fallback_devices(self, mock_run, device):
        """Test fallback to alternative devices"""
        # Setup
        # First 3 devices fail, 4th succeeds
        mock_results = []
        for i in range(3):
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = f"Device error {i}"
            mock_results.append(mock_result)
        
        success_result = Mock()
        success_result.returncode = 0
        mock_results.append(success_result)
        
        mock_run.side_effect = mock_results
        
        # Execute
        result = device.play("/tmp/audio.wav")
        
        # Verify
        assert result is True
        assert mock_run.call_count == 4
        
        # Last call is to successful device
        last_call = mock_run.call_args_list[-1][0][0]
        assert last_call[2] == 'plughw:0,0'  # 4th device
    
    @patch('subprocess.run')
    def test_play_all_devices_fail(self, mock_run, device):
        """Test failure on all devices"""
        # Setup
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Device error"
        mock_run.return_value = mock_result
        
        # Execute
        result = device.play("/tmp/audio.wav")
        
        # Verify
        assert result is False
        assert mock_run.call_count == 4  # Try all alternative devices
    
    @patch('subprocess.run')
    def test_play_exception(self, mock_run, device):
        """Test exception handling"""
        # Setup
        mock_run.side_effect = Exception("Subprocess error")
        
        # Execute
        result = device.play("/tmp/audio.wav")
        
        # Verify
        assert result is False
        assert mock_run.call_count == 4  # Try all alternative devices
    
    def test_update_config(self, device):
        """Test configuration update"""
        # Setup
        new_config = {
            "speaker_device": "hw:1,0",
            "volume": 0.8,
            "sample_rate": 48000
        }
        
        # Execute
        device.update_config(new_config)
        
        # Verify
        assert device.speaker_device == "hw:1,0"
        assert device.volume == 0.8
        assert device.sample_rate == 48000