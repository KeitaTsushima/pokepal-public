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


class TestAudioDeviceAsyncPlayback:
    """Tests for async playback and barge-in support (Step 3.1)"""

    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader for AudioDevice"""
        mock = Mock()
        mock.get.side_effect = lambda key, default=None: {
            'audio.speaker_device': 'plughw:2,0',
            'audio.mic_device': 'plughw:3,0',
            'audio.volume': 1.0,
            'audio.sample_rate': 16000,
        }.get(key, default)
        return mock

    @pytest.fixture
    def device(self, mock_config_loader):
        """AudioDevice instance for testing"""
        return AudioDevice(mock_config_loader)

    @pytest.mark.asyncio
    @patch('infrastructure.audio.audio_device.subprocess.Popen')
    async def test_play_file_async_success(self, mock_popen, device):
        """Test successful async playback"""
        # Setup mock process
        mock_process = Mock()
        mock_process.communicate.return_value = (None, b'')
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Execute
        result = await device.play_file_async("/tmp/test.wav")

        # Verify
        assert result is True
        mock_popen.assert_called_once()
        assert device._playback_process is None  # Cleared after completion

    @pytest.mark.asyncio
    @patch('infrastructure.audio.audio_device.subprocess.Popen')
    async def test_play_file_async_barge_in(self, mock_popen, device):
        """Test async playback stopped by barge-in (SIGTERM)"""
        # Setup mock process - terminated by SIGTERM
        mock_process = Mock()
        mock_process.communicate.return_value = (None, b'')
        mock_process.returncode = -15  # SIGTERM
        mock_popen.return_value = mock_process

        # Execute
        result = await device.play_file_async("/tmp/test.wav")

        # Verify - should return False when stopped by barge-in
        assert result is False
        assert device._playback_process is None

    def test_stop_terminates_tracked_process(self, device):
        """Test stop() terminates the tracked playback process"""
        # Setup - simulate a running process
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.wait.return_value = None
        device._playback_process = mock_process

        # Execute
        device.stop()

        # Verify
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=0.5)
        assert device._playback_process is None

    def test_stop_kills_stubborn_process(self, device):
        """Test stop() kills process if terminate times out"""
        import subprocess

        # Setup - simulate a stubborn process that doesn't terminate
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running
        mock_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd='aplay', timeout=0.5),  # First wait times out
            None  # Second wait succeeds after kill
        ]
        device._playback_process = mock_process

        # Execute
        device.stop()

        # Verify
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.wait.call_count == 2
        assert device._playback_process is None

    def test_stop_no_process(self, device):
        """Test stop() when no process is running"""
        # Setup - no process running
        assert device._playback_process is None

        # Execute - should not raise any exception
        device.stop()

        # Verify - still None, no error
        assert device._playback_process is None