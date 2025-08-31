"""
Unit tests for TTSCoreSynthesizer
TTS Core Synthesizer implementation tests
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys
import os

# External dependencies mocking
sys.modules['httpx'] = MagicMock()
sys.modules['azure'] = MagicMock()
sys.modules['azure.keyvault'] = MagicMock()
sys.modules['azure.keyvault.secrets'] = MagicMock()
sys.modules['azure.keyvault.secrets.aio'] = MagicMock()
sys.modules['azure.identity'] = MagicMock()
sys.modules['azure.identity.aio'] = MagicMock()
sys.modules['azure.cognitiveservices'] = MagicMock()
sys.modules['azure.cognitiveservices.speech'] = MagicMock()
sys.modules['openai'] = MagicMock()

from infrastructure.ai.tts_core_synthesizer import TTSCoreSynthesizer


class TestTTSCoreSynthesizer:
    """Test class for TTSCoreSynthesizer"""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock for ConfigLoader"""
        mock = Mock()
        mock.get.side_effect = lambda key, default=None: {
            'tts.provider': 'openai',
            'tts.model': 'tts-1',
            'tts.voice': 'nova',
            'tts.azure.region': 'japaneast',
            'tts.azure.voice': 'ja-JP-NanamiNeural'
        }.get(key, default)
        return mock
    
    @pytest.fixture
    def synthesizer(self, mock_config_loader):
        """Synthesizer for testing"""
        with patch.dict(os.environ, {
            'OPENAI_SECRET_NAME': 'test-secret',
            'AZURE_SPEECH_KEY': 'test-key'
        }):
            return TTSCoreSynthesizer(mock_config_loader)
    
    @pytest.mark.asyncio
    async def test_openai_synthesis(self, synthesizer):
        """Test OpenAI TTS synthesis"""
        synthesizer.provider = 'openai'
        
        with patch('infrastructure.ai.tts_core_synthesizer.get_shared_openai') as mock_get:
            mock_shared = AsyncMock()
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.content = b'audio_data'
            mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
            mock_shared.get_tts_client = AsyncMock(return_value=mock_client)
            mock_get.return_value = mock_shared
            
            result = await synthesizer.synthesize("Test", "/tmp/output.wav")
            
            assert result == "/tmp/output.wav"
            mock_client.audio.speech.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_azure_synthesis(self, synthesizer):
        """Test Azure TTS synthesis"""
        synthesizer.provider = 'azure'
        
        with patch('azure.cognitiveservices.speech.SpeechConfig') as mock_config:
            with patch('azure.cognitiveservices.speech.SpeechSynthesizer') as mock_synth:
                mock_instance = Mock()
                mock_result = Mock()
                mock_result.reason = 0  # Success
                mock_result.audio_data = b'audio_data'
                mock_instance.speak_text_async.return_value.get.return_value = mock_result
                mock_synth.return_value = mock_instance
                
                result = await synthesizer.synthesize("Test", "/tmp/output.wav")
                
                assert result == "/tmp/output.wav"
    
    @pytest.mark.asyncio
    async def test_provider_switching(self, synthesizer):
        """Test provider switching"""
        # Switch to Azure
        synthesizer.switch_provider('azure')
        assert synthesizer.provider == 'azure'
        
        # Switch to OpenAI
        synthesizer.switch_provider('openai')
        assert synthesizer.provider == 'openai'
        
        # Invalid provider
        with pytest.raises(ValueError):
            synthesizer.switch_provider('invalid')
    
    @pytest.mark.asyncio
    async def test_voice_selection(self, synthesizer):
        """Test voice selection"""
        # OpenAI voices
        openai_voices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        for voice in openai_voices:
            synthesizer.set_voice(voice, provider='openai')
            assert synthesizer.openai_voice == voice
        
        # Azure voices
        azure_voices = ['ja-JP-NanamiNeural', 'ja-JP-KeitaNeural']
        for voice in azure_voices:
            synthesizer.set_voice(voice, provider='azure')
            assert synthesizer.azure_voice == voice
    
    @pytest.mark.asyncio
    async def test_synthesis_with_ssml(self, synthesizer):
        """Test synthesis with SSML"""
        ssml = """
        <speak>
            <prosody rate="1.2" pitch="+2st">
                Hello
            </prosody>
        </speak>
        """
        
        synthesizer.provider = 'azure'
        
        with patch('azure.cognitiveservices.speech.SpeechSynthesizer') as mock_synth:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.reason = 0
            mock_instance.speak_ssml_async.return_value.get.return_value = mock_result
            mock_synth.return_value = mock_instance
            
            result = await synthesizer.synthesize_ssml(ssml, "/tmp/output.wav")
            
            assert result == "/tmp/output.wav"
            mock_instance.speak_ssml_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_streaming_synthesis(self, synthesizer):
        """Test streaming synthesis"""
        async def mock_stream():
            yield b'chunk1'
            yield b'chunk2'
            yield b'chunk3'
        
        synthesizer.provider = 'openai'
        
        with patch.object(synthesizer, 'synthesize_stream', return_value=mock_stream()):
            chunks = []
            async for chunk in synthesizer.synthesize_stream("test"):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks == [b'chunk1', b'chunk2', b'chunk3']
    
    @pytest.mark.asyncio
    async def test_synthesis_error_handling(self, synthesizer):
        """Test synthesis error handling"""
        synthesizer.provider = 'openai'
        
        with patch('infrastructure.ai.tts_core_synthesizer.get_shared_openai') as mock_get:
            mock_get.side_effect = Exception("API Error")
            
            result = await synthesizer.synthesize("test", "/tmp/output.wav")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_fallback_provider(self, synthesizer):
        """Test fallback provider"""
        synthesizer.provider = 'openai'
        synthesizer.fallback_provider = 'azure'
        
        # OpenAI fails
        with patch('infrastructure.ai.tts_core_synthesizer.get_shared_openai') as mock_openai:
            mock_openai.side_effect = Exception("OpenAI Error")
            
            # Azure succeeds
            with patch('azure.cognitiveservices.speech.SpeechSynthesizer') as mock_azure:
                mock_instance = Mock()
                mock_result = Mock()
                mock_result.reason = 0
                mock_instance.speak_text_async.return_value.get.return_value = mock_result
                mock_azure.return_value = mock_instance
                
                result = await synthesizer.synthesize_with_fallback("test", "/tmp/output.wav")
                
                assert result == "/tmp/output.wav"
    
    @pytest.mark.asyncio
    async def test_cache_synthesis_results(self, synthesizer):
        """Test synthesis result caching"""
        synthesizer.enable_cache = True
        synthesizer.cache = {}
        
        # First synthesis
        with patch.object(synthesizer, '_synthesize_internal', return_value="/tmp/output.wav"):
            result1 = await synthesizer.synthesize("test", "/tmp/output1.wav")
            assert result1 == "/tmp/output.wav"
            assert "test" in synthesizer.cache
        
        # Second synthesis (from cache)
        result2 = await synthesizer.synthesize("test", "/tmp/output2.wav")
        assert result2 == synthesizer.cache["test"]
    
    @pytest.mark.asyncio
    async def test_language_detection(self, synthesizer):
        """Test language detection"""
        # Japanese
        lang = synthesizer.detect_language("\u3053\u3093\u306b\u3061\u306f")
        assert lang == "ja"
        
        # English
        lang = synthesizer.detect_language("Hello world")
        assert lang == "en"
        
        # Chinese
        lang = synthesizer.detect_language("\u4f60\u597d\u4e16\u754c")
        assert lang == "zh"
    
    @pytest.mark.asyncio
    async def test_output_format_conversion(self, synthesizer):
        """Test output format conversion"""
        formats = ['wav', 'mp3', 'ogg', 'opus']
        
        for fmt in formats:
            synthesizer.output_format = fmt
            
            with patch.object(synthesizer, '_convert_audio_format', return_value=f"/tmp/output.{fmt}"):
                result = await synthesizer.synthesize("test", f"/tmp/output.{fmt}")
                assert result.endswith(f".{fmt}")
    
    @pytest.mark.asyncio
    async def test_batch_synthesis(self, synthesizer):
        """Test batch synthesis"""
        texts = ["Text1", "Text2", "Text3"]
        
        with patch.object(synthesizer, 'synthesize', side_effect=[f"/tmp/output{i}.wav" for i in range(3)]):
            results = await synthesizer.batch_synthesize(texts)
            
            assert len(results) == 3
            assert all(r.endswith(".wav") for r in results)