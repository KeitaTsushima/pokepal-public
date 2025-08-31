"""
OpenAI API contract tests
API schema validation and contract testing
"""
import pytest
import json
from typing import Dict, Any


class TestOpenAIContract:
    """Contract tests for OpenAI API"""
    
    def validate_request_schema(self, request: Dict[str, Any]) -> bool:
        """Validate request schema"""
        required_fields = ['model', 'messages']
        
        # Check required fields
        for field in required_fields:
            if field not in request:
                return False
        
        # Validate messages structure
        if not isinstance(request['messages'], list):
            return False
        
        for message in request['messages']:
            if 'role' not in message or 'content' not in message:
                return False
            if message['role'] not in ['system', 'user', 'assistant']:
                return False
        
        return True
    
    def validate_response_schema(self, response: Dict[str, Any]) -> bool:
        """Validate response schema"""
        # Check basic structure
        if 'choices' not in response:
            return False
        
        if not isinstance(response['choices'], list):
            return False
        
        # Check structure within choices
        for choice in response['choices']:
            if 'message' not in choice:
                return False
            if 'content' not in choice['message']:
                return False
        
        return True
    
    def test_chat_completion_request_contract(self):
        """Contract test for Chat Completion API request"""
        # Expected request format
        valid_request = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        assert self.validate_request_schema(valid_request) is True
        
        # Invalid request formats
        invalid_requests = [
            # Missing model field
            {
                "messages": [{"role": "user", "content": "test"}]
            },
            # Messages not an array
            {
                "model": "gpt-4",
                "messages": "invalid"
            },
            # Invalid role
            {
                "model": "gpt-4",
                "messages": [{"role": "invalid", "content": "test"}]
            }
        ]
        
        for invalid_req in invalid_requests:
            assert self.validate_request_schema(invalid_req) is False
    
    def test_chat_completion_response_contract(self):
        """Contract test for Chat Completion API response"""
        # Expected response format
        valid_response = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you?"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 9,
                "completion_tokens": 12,
                "total_tokens": 21
            }
        }
        
        assert self.validate_response_schema(valid_response) is True
        
        # Invalid response formats
        invalid_responses = [
            # Missing choices field
            {
                "id": "chatcmpl-123",
                "usage": {"total_tokens": 21}
            },
            # Missing message in choices
            {
                "choices": [{"index": 0}]
            }
        ]
        
        for invalid_resp in invalid_responses:
            assert self.validate_response_schema(invalid_resp) is False
    
    def test_streaming_response_contract(self):
        """Contract test for streaming response"""
        # Streaming chunk format
        valid_chunk = {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": "Hello"
                },
                "finish_reason": None
            }]
        }
        
        # Check delta field
        assert 'choices' in valid_chunk
        assert 'delta' in valid_chunk['choices'][0]
        
    def test_whisper_transcription_contract(self):
        """Contract test for Whisper API (STT)"""
        # Request format (multipart/form-data)
        request_fields = {
            "file": "audio_file",  # Required
            "model": "whisper-1",  # Required
            "language": "ja",      # Optional
            "response_format": "text"  # Optional
        }
        
        # Check required fields
        assert "file" in request_fields
        assert "model" in request_fields
        
        # Response format
        valid_response_text = "This is the transcription of test audio."
        assert isinstance(valid_response_text, str)
        
        valid_response_json = {
            "text": "This is the transcription of test audio."
        }
        assert "text" in valid_response_json
    
    def test_tts_synthesis_contract(self):
        """Contract test for TTS API"""
        # Request format
        valid_request = {
            "model": "tts-1",
            "input": "Hello, how are you?",
            "voice": "nova",
            "response_format": "mp3",
            "speed": 1.0
        }
        
        # Required fields
        required = ["model", "input", "voice"]
        for field in required:
            assert field in valid_request
        
        # Validate voice options
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        assert valid_request["voice"] in valid_voices
        
        # Response is audio binary data
        # Content-Type: audio/mpeg or audio/wav
    
    def test_error_response_contract(self):
        """Contract test for error response"""
        # Standard error format
        error_response = {
            "error": {
                "message": "Invalid API key provided",
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key"
            }
        }
        
        assert "error" in error_response
        assert "message" in error_response["error"]
        assert "type" in error_response["error"]
        
        # Validate error types
        valid_error_types = [
            "invalid_request_error",
            "authentication_error",
            "rate_limit_error",
            "server_error"
        ]
        assert error_response["error"]["type"] in valid_error_types