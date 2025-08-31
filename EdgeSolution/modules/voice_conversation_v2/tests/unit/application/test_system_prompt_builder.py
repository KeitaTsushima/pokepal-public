"""
Unit tests for SystemPromptBuilder
Tests for system prompt construction service
"""
import pytest
from unittest.mock import Mock, MagicMock
from application.system_prompt_builder import (
    SystemPromptBuilder, SystemPromptBuilderError
)


class TestSystemPromptBuilder:
    """Test class for SystemPromptBuilder"""
    
    @pytest.fixture
    def mock_memory_repository(self):
        """Mock MemoryRepository"""
        repository = Mock()
        repository.get_current_memory.return_value = {
            "memory": {
                "short_term_memory": "昨日は花子さんと庭の花について話しました。",
                "user_context": {
                    "preferences": ["花が好き", "音楽鑑賞", "読書"],
                    "concerns": ["最近物忘れが多い", "膝の調子が悪い"]
                }
            }
        }
        return repository
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        config = Mock()
        config.get.side_effect = lambda key, default=None: {
            "llm.system_prompt": "あなたは{user_name}さんの話し相手です。",
            "llm.user_name": "田中太郎",
            "llm.memory_format": {
                "short_term_memory": "【最近の会話】{content}",
                "preferences": "【好きなこと】{content}",
                "concerns": "【気になること】{content}"
            },
            "memory.max_items_per_section": {
                "preferences": 3,
                "concerns": 2
            }
        }.get(key, default)
        return config
    
    @pytest.fixture
    def builder(self, mock_memory_repository, mock_config_loader):
        """Builder under test"""
        return SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
    
    def test_init_with_valid_config(self, mock_memory_repository, mock_config_loader):
        """Test initialization with valid config"""
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        assert builder._memory_repository == mock_memory_repository
        assert builder._config_loader == mock_config_loader
    
    def test_init_without_config_loader(self, mock_memory_repository):
        """Test initialization without config_loader (error)"""
        with pytest.raises(ValueError, match="config_loader is required"):
            SystemPromptBuilder(
                memory_repository=mock_memory_repository,
                config_loader=None
            )
    
    def test_init_without_memory_repository(self, mock_config_loader):
        """Test initialization without memory_repository (allowed)"""
        builder = SystemPromptBuilder(
            memory_repository=None,
            config_loader=mock_config_loader
        )
        assert builder._memory_repository is None
        assert builder._config_loader == mock_config_loader
    
    def test_build_system_prompt_with_memory(self, builder):
        """Test prompt construction with memory information"""
        result = builder.build_system_prompt()
        
        # Basic prompt
        assert "あなたは田中太郎さんの話し相手です。" in result
        
        # Memory information
        assert "【最近の会話】昨日は花子さんと庭の花について話しました。" in result
        assert "【好きなこと】花が好き、音楽鑑賞、読書" in result
        assert "【気になること】最近物忘れが多い、膝の調子が悪い" in result
    
    def test_build_system_prompt_without_memory(self, mock_config_loader):
        """Test prompt construction without memory"""
        builder = SystemPromptBuilder(
            memory_repository=None,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        
        # Basic prompt only
        assert result == "あなたは田中太郎さんの話し相手です。"
    
    def test_build_system_prompt_without_user_name(self, mock_memory_repository, mock_config_loader):
        """Test prompt construction without user name"""
        mock_config_loader.get.side_effect = lambda key, default=None: {
            "llm.system_prompt": "あなたは高齢者の話し相手です。",
            "llm.user_name": "",  # Empty string
            "llm.memory_format": {
                "short_term_memory": "【最近の会話】{content}",
                "preferences": "【好きなこと】{content}",
                "concerns": "【気になること】{content}"
            },
            "memory.max_items_per_section": {
                "preferences": 3,
                "concerns": 2
            }
        }.get(key, default)
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        assert "あなたは高齢者の話し相手です。" in result
    
    def test_build_system_prompt_with_partial_memory(self, mock_memory_repository, mock_config_loader):
        """Test with only partial memory information"""
        # Only short_term_memory exists
        mock_memory_repository.get_current_memory.return_value = {
            "memory": {
                "short_term_memory": "今朝は散歩に行きました。",
                "user_context": {}  # No preferences and concerns
            }
        }
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        
        assert "【最近の会話】今朝は散歩に行きました。" in result
        assert "【好きなこと】" not in result
        assert "【気になること】" not in result
    
    def test_build_system_prompt_with_max_items_limit(self, mock_memory_repository, mock_config_loader):
        """Test max items limit"""
        # Set many items
        mock_memory_repository.get_current_memory.return_value = {
            "memory": {
                "short_term_memory": "最近の会話",
                "user_context": {
                    "preferences": ["項目1", "項目2", "項目3", "項目4", "項目5"],
                    "concerns": ["心配1", "心配2", "心配3"]
                }
            }
        }
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        
        # preferences has max 3 items
        assert "【好きなこと】項目1、項目2、項目3" in result
        assert "項目4" not in result
        assert "項目5" not in result
        
        # concerns has max 2 items
        assert "【気になること】心配1、心配2" in result
        assert "心配3" not in result
    
    def test_build_system_prompt_error_handling(self, mock_memory_repository, mock_config_loader):
        """Test error handling"""
        # Raise error in config_loader
        mock_config_loader.get.side_effect = Exception("Config error")
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        with pytest.raises(SystemPromptBuilderError, match="Failed to build system prompt"):
            builder.build_system_prompt()
    
    def test_build_memory_sections_error_handling(self, builder, mock_memory_repository):
        """Test error handling in memory section construction"""
        # Raise error in memory retrieval
        mock_memory_repository.get_current_memory.side_effect = Exception("Memory error")
        
        with pytest.raises(SystemPromptBuilderError, match="Failed to build system prompt"):
            builder.build_system_prompt()
    
    def test_build_system_prompt_empty_memory(self, mock_memory_repository, mock_config_loader):
        """Test prompt construction with empty memory"""
        mock_memory_repository.get_current_memory.return_value = {
            "memory": {
                "user_context": {}
            }
        }
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        
        # Only basic prompt is returned
        assert result == "あなたは田中太郎さんの話し相手です。"
    
    def test_build_system_prompt_with_format_placeholder(self, mock_memory_repository, mock_config_loader):
        """Test format placeholder processing"""
        mock_config_loader.get.side_effect = lambda key, default=None: {
            "llm.system_prompt": "こんにちは、{user_name}さん。今日も良い一日を！",
            "llm.user_name": "山田花子",
            "llm.memory_format": {
                "short_term_memory": "記憶: {content}",
                "preferences": "好み: {content}",
                "concerns": "気がかり: {content}"
            },
            "memory.max_items_per_section": {
                "preferences": 5,
                "concerns": 3
            }
        }.get(key, default)
        
        builder = SystemPromptBuilder(
            memory_repository=mock_memory_repository,
            config_loader=mock_config_loader
        )
        
        result = builder.build_system_prompt()
        
        assert "こんにちは、山田花子さん。今日も良い一日を！" in result
        assert "記憶: 昨日は花子さんと庭の花について話しました。" in result