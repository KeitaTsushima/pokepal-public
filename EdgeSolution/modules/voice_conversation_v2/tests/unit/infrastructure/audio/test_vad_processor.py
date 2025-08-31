"""
Unit tests for VADProcessor
Tests voice activity detection implementation (new API compatible)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys

# Mock webrtcvad module
sys.modules['webrtcvad'] = MagicMock()

from infrastructure.audio.vad_processor import VADProcessor


class TestVADProcessor:
    """Test class for VADProcessor"""
    
    @pytest.fixture
    @patch('infrastructure.audio.vad_processor.webrtcvad.Vad')
    def processor(self, mock_vad_class):
        """Processor under test"""
        mock_vad = Mock()
        mock_vad_class.return_value = mock_vad
        return VADProcessor(sample_rate=16000, vad_mode=2)
    
    @patch('infrastructure.audio.vad_processor.webrtcvad.Vad')
    def test_init_with_defaults(self, mock_vad_class):
        """Test initialization with default values"""
        # Execute
        processor = VADProcessor()
        
        # Verify
        assert processor.sample_rate == 16000
        assert processor.vad_mode == 2
        mock_vad_class.assert_called_once_with(2)
    
    @patch('infrastructure.audio.vad_processor.webrtcvad.Vad')
    def test_init_with_custom_values(self, mock_vad_class):
        """Test initialization with custom values"""
        # Execute
        processor = VADProcessor(sample_rate=8000, vad_mode=3)
        
        # Verify
        assert processor.sample_rate == 8000
        assert processor.vad_mode == 3
        mock_vad_class.assert_called_once_with(3)
    
    def test_detect_speech_in_frame_returns_true(self, processor):
        """Test speech frame detection (with speech)"""
        # Setup
        audio_frame = b'\xFF' * 960
        processor.vad.is_speech.return_value = True
        
        # Execute
        result = processor.detect_speech_in_frame(audio_frame)
        
        # Verify
        assert result is True
        processor.vad.is_speech.assert_called_once_with(audio_frame, 16000)
    
    def test_detect_speech_in_frame_returns_false(self, processor):
        """Test speech frame detection (without speech)"""
        # Setup
        audio_frame = b'\x00' * 960
        processor.vad.is_speech.return_value = False
        
        # Execute
        result = processor.detect_speech_in_frame(audio_frame)
        
        # Verify
        assert result is False
        processor.vad.is_speech.assert_called_once_with(audio_frame, 16000)
    
    def test_update_vad_mode_changes_mode(self, processor):
        """Test VAD mode update (with change)"""
        # Setup
        new_mode = 3
        
        # Execute
        with patch('infrastructure.audio.vad_processor.webrtcvad.Vad') as mock_vad_class:
            new_vad = Mock()
            mock_vad_class.return_value = new_vad
            processor.update_vad_mode(new_mode)
        
        # Verify
        assert processor.vad_mode == 3
        assert processor.vad == new_vad
        mock_vad_class.assert_called_once_with(3)
    
    def test_update_vad_mode_no_change(self, processor):
        """Test VAD mode update (no change)"""
        # Setup
        original_vad = processor.vad
        same_mode = 2  # Same as initial value
        
        # Execute
        with patch('infrastructure.audio.vad_processor.webrtcvad.Vad') as mock_vad_class:
            processor.update_vad_mode(same_mode)
        
        # Verify
        assert processor.vad_mode == 2
        assert processor.vad == original_vad  # VAD object unchanged
        mock_vad_class.assert_not_called()
    
    def test_detect_speech_uses_correct_sample_rate(self, processor):
        """Test speech detection with custom sampling rate"""
        # Setup: Create 8kHz processor
        with patch('infrastructure.audio.vad_processor.webrtcvad.Vad') as mock_vad_class:
            mock_vad = Mock()
            mock_vad_class.return_value = mock_vad
            processor_8k = VADProcessor(sample_rate=8000, vad_mode=1)
            
            audio_frame = b'\xFF' * 480  # 480 bytes/frame at 8kHz
            mock_vad.is_speech.return_value = True
            
            # Execute
            result = processor_8k.detect_speech_in_frame(audio_frame)
            
            # Verify
            assert result is True
            mock_vad.is_speech.assert_called_once_with(audio_frame, 8000)