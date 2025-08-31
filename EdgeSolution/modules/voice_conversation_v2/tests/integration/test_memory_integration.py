"""
Memory System Integration Tests

Tests the complete flow from memory loading, 
integration into conversations, to persistence.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from domain.conversation import Conversation, ConversationConfig
from application.conversation_service import ConversationService
from infrastructure.memory.memory_repository import MemoryRepository


class TestMemoryIntegration:
    """Memory system integration tests"""
    
    @pytest.fixture
    def test_memories_dir(self, tmp_path):
        """Test memory directory"""
        memories_dir = tmp_path / "memories"
        memories_dir.mkdir()
        return str(memories_dir)
    
    @pytest.fixture
    def sample_memory_data(self):
        """Sample memory data"""
        return {
            "date": "2025-07-01",
            "short_term": [
                {
                    "time": "09:00",
                    "date": "2025-07-01",
                    "summary": "Exchanged morning greetings and talked about today's schedule"
                },
                {
                    "time": "10:30", 
                    "date": "2025-07-01",
                    "summary": "Looked happy talking about grandchildren"
                }
            ],
            "medium_term": [
                {
                    "date_range": "2025-06-24 - 2025-06-30",
                    "summary": "Had many days feeling unwell last week"
                },
                {
                    "date_range": "2025-06-17 - 2025-06-23",
                    "summary": "Looked happy when daughter visited"
                }
            ],
            "long_term": [
                {
                    "summary": "Family-oriented, eyes light up when talking about grandchildren"
                },
                {
                    "summary": "Health-conscious, never misses daily walks"
                }
            ]
        }
    
    def test_memory_repository_file_operations(self, test_memories_dir, sample_memory_data):
        """Test MemoryRepository file operations"""
        # Create memory file
        memory_file = Path(test_memories_dir) / "memory_20250701.json"
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(sample_memory_data, f, ensure_ascii=False, indent=2)
        
        # Load with MemoryRepository
        repo = MemoryRepository(memories_dir=test_memories_dir)
        memory = repo.get_latest_memory()
        
        # Verify
        assert memory is not None
        assert memory['date'] == "2025-07-01"
        assert len(memory['short_term']) == 2
        assert len(memory['medium_term']) == 2
        assert len(memory['long_term']) == 2
    
    def test_memory_repository_no_memory_file(self, test_memories_dir):
        """Test when memory file does not exist"""
        repo = MemoryRepository(memories_dir=test_memories_dir)
        memory = repo.get_latest_memory()
        
        # Returns None when no memory found
        assert memory is None
    
    def test_conversation_service_with_memory(self, test_memories_dir, sample_memory_data):
        """Test ConversationService integration with memory system"""
        # Create memory file
        memory_file = Path(test_memories_dir) / "memory_20250701.json"
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(sample_memory_data, f, ensure_ascii=False, indent=2)
        
        # Prepare mocks
        mock_ai_client = Mock()
        mock_telemetry = Mock()
        mock_audio_output = Mock()
        
        # Create ConversationService
        config = ConversationConfig(
            max_tokens=25000,
            default_system_prompt="You are a conversation partner for the elderly.",
            farewell_message="Understood. Let's talk again.",
            llm_model_name="gpt-4o-mini",
            tokenizer_encoding_method="cl100k_base"
        )
        
        repo = MemoryRepository(memories_dir=test_memories_dir)
        
        service = ConversationService(
            config=config,
            ai_client=mock_ai_client,
            memory_repository=repo,
            telemetry_adapter=mock_telemetry
        )
        
        # Test system prompt building
        system_prompt = service._build_system_prompt()
        
        # Verify memory is included
        assert "Exchanged morning greetings and talked about today's schedule" in system_prompt
        assert "Looked happy talking about grandchildren" in system_prompt
        assert "Family-oriented, eyes light up when talking about grandchildren" in system_prompt
    
    
    def test_memory_integration_full_flow(self, test_memories_dir, tmp_path):
        """Complete memory system integration flow"""
        # 1. Prepare previous day's memory file
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        memory_file = Path(test_memories_dir) / f"memory_{yesterday}.json"
        
        yesterday_memory = {
            "date": yesterday,
            "short_term": [
                {"summary": "Was feeling well yesterday and enjoyed the walk"}
            ],
            "long_term": [
                {"summary": "Values daily walks"}
            ]
        }
        
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump(yesterday_memory, f, ensure_ascii=False, indent=2)
        
        # 2. Initialize ConversationService
        mock_ai_client = Mock()
        mock_ai_client.generate_response.return_value = "It's a perfect day for a walk today! Glad you enjoyed yesterday's walk."
        
        config = ConversationConfig(
            max_tokens=25000,
            default_system_prompt="You are a conversation partner for the elderly.",
            farewell_message="Understood. Let's talk again.",
            llm_model_name="gpt-4o-mini",
            tokenizer_encoding_method="cl100k_base"
        )
        
        repo = MemoryRepository(memories_dir=test_memories_dir)
        
        service = ConversationService(
            config=config,
            ai_client=mock_ai_client,
            memory_repository=repo,
            telemetry_adapter=Mock()
        )
        
        # 3. Execute conversation
        service.start()
        response = service.handle_user_input("Maybe I'll go for a walk today")
        
        # 4. Verify: AI references memory in response
        assert response is not None
        call_args = mock_ai_client.generate_response.call_args[0][0]
        system_message = call_args[0]
        assert "Was feeling well yesterday and enjoyed the walk" in system_message['content']
        
