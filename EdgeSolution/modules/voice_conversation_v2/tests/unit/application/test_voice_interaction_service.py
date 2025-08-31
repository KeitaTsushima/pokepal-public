"""
Unit tests for VoiceInteractionService
Tests core voice interaction service functionality
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
from application.voice_interaction_service import VoiceInteractionService
from domain.conversation import MessageRole


class TestVoiceInteractionService:
    """Test class for VoiceInteractionService"""
    
    @pytest.fixture
    def mock_conversation_service(self):
        """Mock for ConversationService"""
        service = Mock()
        service.conversation = Mock()
        service.conversation.is_sleeping.return_value = False
        service.conversation.enter_sleep = Mock()
        service.conversation.exit_sleep = Mock()
        service.is_exit_command.return_value = False
        service.handle_exit_command.return_value = "Goodbye"
        service.generate_response_stream = AsyncMock()
        service._record_and_send_utterance = Mock()
        service.end_session = Mock()
        return service
    
    @pytest.fixture
    def mock_audio_capture(self):
        """Mock for AudioCapture"""
        capture = Mock()
        capture.capture_audio.return_value = "/tmp/audio.wav"
        capture.cleanup = Mock()
        return capture
    
    @pytest.fixture
    def mock_speech_to_text(self):
        """Mock for SpeechToText"""
        stt = AsyncMock()
        stt.transcribe.return_value = "Hello"
        return stt
    
    @pytest.fixture
    def mock_audio_output(self):
        """Mock for AudioOutput"""
        output = Mock()
        output.speech_announcement = AsyncMock()
        output.speech_segment_streaming = AsyncMock()
        output.start_streaming_session = Mock(return_value=True)
        output.stop_streaming_session = AsyncMock()
        output.stop_audio_for_barge_in = Mock()
        output.cleanup = Mock()
        return output
    
    @pytest.fixture
    def voice_service(self, mock_conversation_service, mock_audio_capture, 
                     mock_speech_to_text, mock_audio_output):
        """Service under test"""
        return VoiceInteractionService(
            conversation_service=mock_conversation_service,
            audio_capture=mock_audio_capture,
            speech_to_text=mock_speech_to_text,
            audio_output=mock_audio_output,
            no_voice_sleep_threshold=5
        )
    
    @pytest.mark.asyncio
    async def test_initialize(self, voice_service, mock_audio_output):
        """Test initialization process"""
        await voice_service.initialize()
        
        mock_audio_output.speech_announcement.assert_called_once_with(
            "Hello! PokePal voice interaction system has started."
        )
    
    @pytest.mark.asyncio
    async def test_process_conversation_normal_flow(self, voice_service, mock_conversation_service,
                                                   mock_audio_capture, mock_speech_to_text, 
                                                   mock_audio_output):
        """Test normal conversation processing flow"""
        # Mock generate_response_stream - returns async generator when called
        call_tracker = []
        async def mock_stream(text):
            call_tracker.append(text)
            yield {"type": "segment", "text": "Hello, "}
            yield {"type": "segment", "text": "how are you?"}
            yield {"type": "final", "text": "Hello, how are you?"}
        
        # Replace generate_response_stream method
        mock_conversation_service.generate_response_stream = mock_stream
        mock_conversation_service._stream_call_tracker = call_tracker  # For test verification
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify
        mock_audio_capture.capture_audio.assert_called_once()
        mock_audio_output.stop_audio_for_barge_in.assert_called_once()
        mock_speech_to_text.transcribe.assert_called_once_with("/tmp/audio.wav")
        assert call_tracker == ["Hello"]  # generate_response_stream called with correct argument
        assert mock_audio_output.speech_segment_streaming.call_count == 2
        mock_audio_output.start_streaming_session.assert_called_once()
        mock_audio_output.stop_streaming_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_conversation_no_audio(self, voice_service, mock_audio_capture):
        """Test processing with no audio input"""
        mock_audio_capture.capture_audio.return_value = None
        
        await voice_service.process_conversation()
        
        assert voice_service.no_voice_count == 1
    
    @pytest.mark.asyncio
    async def test_process_conversation_empty_transcription(self, voice_service, mock_speech_to_text):
        """Test when transcription result is empty"""
        mock_speech_to_text.transcribe.return_value = ""
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify LLM processing is not called
        voice_service.conversation_service.generate_response_stream.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_conversation_exit_command(self, voice_service, mock_conversation_service,
                                                    mock_speech_to_text, mock_audio_output):
        """Test exit command processing"""
        mock_speech_to_text.transcribe.return_value = "goodbye"
        mock_conversation_service.is_exit_command.return_value = True
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        mock_conversation_service.handle_exit_command.assert_called_once_with("goodbye")
        mock_audio_output.speech_announcement.assert_called_once_with("Goodbye")
    
    @pytest.mark.asyncio
    async def test_process_conversation_wake_from_sleep(self, voice_service, mock_conversation_service,
                                                       mock_speech_to_text, mock_audio_output):
        """Test waking from sleep mode"""
        mock_conversation_service.conversation.is_sleeping.return_value = True
        
        # Mock generate_response_stream as async generator
        async def mock_stream(text):
            yield {"type": "segment", "text": "I'm awake"}
            yield {"type": "final", "text": "I'm awake"}
        mock_conversation_service.generate_response_stream = mock_stream
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        mock_conversation_service.conversation.exit_sleep.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_conversation_stt_timeout(self, voice_service, mock_speech_to_text):
        """Test STT timeout"""
        mock_speech_to_text.transcribe.side_effect = asyncio.TimeoutError()
        
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            with patch('os.path.exists', return_value=True):
                with patch('os.remove'):
                    await voice_service.process_conversation()
        
        # Verify error is handled and program continues
        assert voice_service.running is True
    
    @pytest.mark.asyncio
    async def test_process_conversation_stt_error(self, voice_service, mock_speech_to_text):
        """Test STT error"""
        mock_speech_to_text.transcribe.side_effect = Exception("STT error")
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify error is handled and program continues
        assert voice_service.running is True
    
    @pytest.mark.asyncio
    async def test_process_conversation_llm_error(self, voice_service, mock_conversation_service,
                                                 mock_audio_output):
        """Test LLM streaming error"""
        # Mock generate_response_stream as async generator
        async def mock_stream(text):
            yield {"type": "error", "text": "An error occurred"}
        mock_conversation_service.generate_response_stream = mock_stream
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify error message is announced
        voice_service.audio_output.speech_announcement.assert_called_with("An error occurred")
    
    @pytest.mark.asyncio
    async def test_process_conversation_tts_segment_error(self, voice_service, mock_conversation_service,
                                                          mock_audio_output):
        """Test TTS segment error"""
        # Mock generate_response_stream as async generator
        async def mock_stream(text):
            yield {"type": "segment", "text": "Error segment"}
            yield {"type": "segment", "text": "Normal segment"}
            yield {"type": "final", "text": "Error segment Normal segment"}
        mock_conversation_service.generate_response_stream = mock_stream
        # First segment errors, second is normal
        mock_audio_output.speech_segment_streaming.side_effect = [
            Exception("TTS error"),
            None
        ]
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify both segments are processed
        assert mock_audio_output.speech_segment_streaming.call_count == 2
    
    def test_handle_no_voice_increments_count(self, voice_service):
        """Test no voice count increment"""
        initial_count = voice_service.no_voice_count
        voice_service._handle_no_voice()
        assert voice_service.no_voice_count == initial_count + 1
    
    def test_handle_no_voice_enters_sleep(self, voice_service, mock_conversation_service):
        """Test entering sleep mode"""
        voice_service.no_voice_count = 4  # One before threshold
        mock_conversation_service.conversation.is_sleeping.return_value = False
        
        voice_service._handle_no_voice()
        
        assert voice_service.no_voice_count == 5
        mock_conversation_service.conversation.enter_sleep.assert_called_once()
    
    def test_handle_no_voice_already_sleeping(self, voice_service, mock_conversation_service):
        """Test when already sleeping"""
        voice_service.no_voice_count = 10
        mock_conversation_service.conversation.is_sleeping.return_value = True
        
        voice_service._handle_no_voice()
        
        # Verify enter_sleep is not called
        mock_conversation_service.conversation.enter_sleep.assert_not_called()
    
    def test_stop(self, voice_service, mock_conversation_service, 
                  mock_audio_capture, mock_audio_output):
        """Test stop processing"""
        voice_service.stop()
        
        assert voice_service.running is False
        mock_conversation_service.end_session.assert_called_once()
        mock_audio_capture.cleanup.assert_called_once()
        mock_audio_output.cleanup.assert_called_once()
    
    def test_stop_with_error(self, voice_service, mock_conversation_service):
        """Test error handling during stop"""
        mock_conversation_service.end_session.side_effect = Exception("Session error")
        
        # Verify stop completes even with error
        voice_service.stop()
        assert voice_service.running is False
    
    def test_cleanup_audio_file_success(self, voice_service):
        """Test successful audio file cleanup"""
        with patch('os.path.exists', return_value=True):
            with patch('os.remove') as mock_remove:
                voice_service._cleanup_audio_file("/tmp/test.wav")
                mock_remove.assert_called_once_with("/tmp/test.wav")
    
    def test_cleanup_audio_file_not_exists(self, voice_service):
        """Test cleanup of non-existent file"""
        with patch('os.path.exists', return_value=False):
            with patch('os.remove') as mock_remove:
                voice_service._cleanup_audio_file("/tmp/nonexistent.wav")
                mock_remove.assert_not_called()
    
    def test_cleanup_audio_file_error(self, voice_service):
        """Test file deletion error"""
        with patch('os.path.exists', return_value=True):
            with patch('os.remove', side_effect=OSError("Permission denied")):
                # Verify no exception is raised
                voice_service._cleanup_audio_file("/tmp/protected.wav")
    
    @pytest.mark.asyncio
    async def test_run_loop(self, voice_service):
        """Test execution loop"""
        # Stop after 3 iterations
        call_count = 0
        async def mock_process():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                voice_service.running = False
        
        voice_service.process_conversation = mock_process
        
        await voice_service.run()
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(self, voice_service):
        """Test keyboard interrupt"""
        async def raise_interrupt():
            raise KeyboardInterrupt()
        
        voice_service.process_conversation = raise_interrupt
        
        await voice_service.run()
        assert voice_service.running is False
    
    @pytest.mark.asyncio
    async def test_run_with_error_continues(self, voice_service):
        """Test continuation after error"""
        error_count = 0
        async def error_then_stop():
            nonlocal error_count
            error_count += 1
            if error_count == 1:
                raise Exception("Test error")
            voice_service.running = False
        
        voice_service.process_conversation = error_then_stop
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await voice_service.run()
        
        assert error_count == 2  # Continues after error
    
    @pytest.mark.asyncio
    async def test_send_telemetry_async(self, voice_service, mock_conversation_service):
        """Test async telemetry sending"""
        await voice_service._send_telemetry_async("user", "Test message")
        
        mock_conversation_service._record_and_send_utterance.assert_called_once_with(
            "user", "Test message"
        )
    
    @pytest.mark.asyncio
    async def test_send_telemetry_async_error(self, voice_service, mock_conversation_service):
        """Test telemetry sending error"""
        mock_conversation_service._record_and_send_utterance.side_effect = Exception("Telemetry error")
        
        # Verify no exception is raised
        await voice_service._send_telemetry_async("user", "Error message")
    
    @pytest.mark.asyncio
    async def test_tts_streaming_session_failure(self, voice_service, mock_conversation_service,
                                                mock_audio_output):
        """Test TTS streaming session start failure"""
        # Mock generate_response_stream as async generator
        async def mock_stream(text):
            yield {"type": "segment", "text": "Test"}
            yield {"type": "final", "text": "Test"}
        mock_conversation_service.generate_response_stream = mock_stream
        mock_audio_output.start_streaming_session.return_value = False  # Session start fails
        
        with patch('os.path.exists', return_value=True):
            with patch('os.remove'):
                await voice_service.process_conversation()
        
        # Verify segment processing is skipped
        mock_audio_output.speech_segment_streaming.assert_not_called()
        # stop_streaming_session is also not called
        mock_audio_output.stop_streaming_session.assert_not_called()