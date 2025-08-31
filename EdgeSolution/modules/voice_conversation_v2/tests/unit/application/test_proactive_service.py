"""
Unit tests for ProactiveService
Tests for new Clean Architecture compliant proactive features
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from application.proactive_service import (
    ProactiveService, TaskSchedulerService, TaskScheduler, 
    ScheduledTask, TaskScope, TaskType, ScheduleType, SchedulePattern,
    TaskExecutionStatus, TaskStatusRecord
)


class TestProactiveService:
    """Test class for ProactiveService"""
    
    @pytest.fixture
    def mock_audio_output(self):
        """Mock AudioOutputAdapter"""
        adapter = Mock()
        adapter.text_to_speech = Mock()
        adapter.speech_announcement = Mock()
        return adapter
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        config_loader = Mock()
        config_loader.get.side_effect = lambda key, default=None: {
            "proactive_data.task_file": "test_tasks.json",
            "proactive_data.queue_log_file": "test_executions.json",
            "proactive_data.check_interval": 5,
            "proactive_data.max_queue_size": 10,
            "proactive_data.default_tasks": [],
            "llm.user_name": "テストユーザー"
        }.get(key, default)
        return config_loader
    
    @pytest.fixture
    def service(self, mock_audio_output, mock_config_loader):
        """Service under test"""
        with patch('application.proactive_service.JsonTaskRepository'):
            return ProactiveService(
                audio_output=mock_audio_output,
                config_loader=mock_config_loader
            )
    
    def test_init(self, service):
        """Test initialization"""
        assert service._scheduler is not None
        assert service._task_scheduler_service is not None
        assert service.config_loader is not None
    
    def test_start_and_stop(self, service):
        """Test start and stop"""
        with patch.object(service._task_scheduler_service, 'start') as mock_service_start:
            with patch.object(service._scheduler, 'start') as mock_scheduler_start:
                service.start()
                mock_service_start.assert_called_once()
                mock_scheduler_start.assert_called_once()
        
        with patch.object(service._scheduler, 'stop') as mock_scheduler_stop:
            with patch.object(service._task_scheduler_service, 'stop') as mock_service_stop:
                service.stop()
                mock_scheduler_stop.assert_called_once()
                mock_service_stop.assert_called_once()
    
    def test_add_task(self, service):
        """Test task addition"""
        task_config = {
            "scope": "common",
            "type": "greeting",
            "name": "朝の挨拶",
            "time": "08:00",
            "message": "おはようございます",
            "schedule": {
                "type": "daily"
            }
        }
        
        with patch.object(service._task_scheduler_service, 'add_task', return_value="test-id") as mock_add:
            task_id = service.add_task(task_config)
            mock_add.assert_called_once_with(task_config)
            assert task_id == "test-id"
    
    def test_update_task(self, service):
        """Test task update"""
        updates = {"message": "新しいメッセージ"}
        
        with patch.object(service._task_scheduler_service, 'update_task') as mock_update:
            service.update_task("test-id", updates)
            mock_update.assert_called_once_with("test-id", updates)
    
    def test_remove_task(self, service):
        """Test task removal"""
        with patch.object(service._task_scheduler_service, 'remove_task') as mock_remove:
            service.remove_task("test-id")
            mock_remove.assert_called_once_with("test-id")
    
    def test_set_conversation_service(self, service):
        """Test ConversationService setting"""
        mock_conversation_service = Mock()
        
        service.set_conversation_service(mock_conversation_service)
        
        assert service._task_scheduler_service._conversation_service == mock_conversation_service
    
    def test_is_running(self, service):
        """Test running state check"""
        # Cannot mock property directly, so mock internal state
        service._scheduler._running = True
        assert service.is_running is True


class TestTaskSchedulerService:
    """Test class for TaskSchedulerService"""
    
    @pytest.fixture
    def mock_task_repository(self):
        """Mock TaskRepository"""
        repo = Mock()
        repo.load_tasks.return_value = []
        repo._write_tasks = Mock()
        return repo
    
    @pytest.fixture
    def mock_audio_output(self):
        """Mock AudioOutput"""
        output = Mock()
        output.text_to_speech = Mock()
        return output
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock ConfigLoader"""
        config_loader = Mock()
        config_loader.get.return_value = ""
        return config_loader
    
    @pytest.fixture
    def scheduler_service(self, mock_task_repository, mock_audio_output, mock_config_loader):
        """Service under test"""
        return TaskSchedulerService(
            task_repository=mock_task_repository,
            audio_output=mock_audio_output,
            conversation_service=None,
            config_loader=mock_config_loader
        )
    
    @pytest.fixture
    def sample_task(self):
        """Sample task"""
        return ScheduledTask(
            id="test-task-1",
            scope=TaskScope.COMMON,
            type=TaskType.GREETING,
            name="朝の挨拶",
            time="08:00",
            message="おはようございます",
            schedule=SchedulePattern(type=ScheduleType.DAILY),
            active=True
        )
    
    def test_init(self, scheduler_service):
        """初期化のテスト"""
        assert scheduler_service._active_tasks == []
        assert scheduler_service._running is False
    
    def test_start_and_stop(self, scheduler_service, mock_task_repository):
        """開始と停止のテスト"""
        scheduler_service.start()
        assert scheduler_service._running is True
        mock_task_repository.load_tasks.assert_called_once()
        
        scheduler_service.stop()
        assert scheduler_service._running is False
    
    def test_add_task_success(self, scheduler_service, mock_task_repository):
        """Test successful task addition"""
        task_config = {
            "scope": "common",
            "type": "greeting", 
            "name": "朝の挨拶",
            "time": "08:00",
            "message": "おはようございます",
            "schedule": {"type": "daily"}
        }
        
        mock_task_repository.load_tasks.return_value = []
        
        task_id = scheduler_service.add_task(task_config)
        
        assert task_id is not None
        mock_task_repository._write_tasks.assert_called_once()
    
    def test_add_task_invalid_config(self, scheduler_service):
        """Test invalid task configuration"""
        invalid_config = {
            "scope": "common",
            "type": "greeting",
            # Missing name and message
            "time": "08:00",
            "schedule": {"type": "daily"}
        }
        
        with pytest.raises(TypeError):  # TypeError in ScheduledTask.__init__
            scheduler_service.add_task(invalid_config)
    
    def test_create_unified_message_single_task(self, scheduler_service, sample_task):
        """Message generation for single task"""
        result = scheduler_service.create_unified_message([sample_task])
        assert result == "おはようございます"
    
    def test_create_unified_message_multiple_tasks_no_llm(self, scheduler_service, sample_task):
        """Fallback message generation for multiple tasks"""
        task2 = ScheduledTask(
            id="test-task-2",
            scope=TaskScope.COMMON,
            type=TaskType.MEDICATION,
            name="薬の時間",
            time="08:00", 
            message="お薬をお飲みください",
            schedule=SchedulePattern(type=ScheduleType.DAILY),
            active=True
        )
        
        result = scheduler_service.create_unified_message([sample_task, task2])
        assert "複数の予定があります" in result
        assert "おはようございます" in result
        assert "お薬をお飲みください" in result


class TestTaskScheduler:
    """Test class for TaskScheduler"""
    
    @pytest.fixture
    def mock_task_scheduler_service(self):
        """Mock TaskSchedulerService"""
        service = Mock()
        service.get_tasks_for_time.return_value = []
        return service
    
    @pytest.fixture
    def mock_audio_output(self):
        """Mock AudioOutput"""
        output = Mock()
        output.text_to_speech = Mock()
        return output
    
    @pytest.fixture
    def task_scheduler(self, mock_task_scheduler_service, mock_audio_output):
        """Scheduler under test"""
        with patch('os.path.exists', return_value=False):
            return TaskScheduler(
                task_scheduler_service=mock_task_scheduler_service,
                audio_output=mock_audio_output,
                check_interval=1,
                queue_log_file="test_log.json",
                max_queue_size=5
            )
    
    def test_init(self, task_scheduler):
        """初期化のテスト"""
        assert task_scheduler._running is False
        assert task_scheduler._task_status_today == {}
    
    def test_load_queue_log_no_file(self, task_scheduler):
        """Test when log file does not exist"""
        with patch('os.path.exists', return_value=False):
            result = task_scheduler._load_queue_log()
            assert result == {}
    
    def test_update_task_status(self, task_scheduler):
        """Test task status update"""
        # Set status beforehand
        task_scheduler._task_status_today["test-task"] = TaskStatusRecord(
            status=TaskExecutionStatus.QUEUED
        )
        
        with patch.object(task_scheduler, '_save_queue_log') as mock_save:
            task_scheduler._update_task_status(
                ["test-task"], 
                TaskExecutionStatus.ANNOUNCED
            )
            
            status = task_scheduler._task_status_today["test-task"]
            assert status.status == TaskExecutionStatus.ANNOUNCED
            assert status.completed_at is not None
            mock_save.assert_called_once()


class TestScheduledTask:
    """Test class for ScheduledTask"""
    
    def test_validate_valid_task(self):
        """Validation of valid task"""
        task = ScheduledTask(
            id="test-1",
            scope=TaskScope.COMMON,
            type=TaskType.GREETING,
            name="テスト",
            time="08:00",
            message="テストメッセージ",
            schedule=SchedulePattern(type=ScheduleType.DAILY),
            active=True
        )
        
        assert task.validate() is True
    
    def test_validate_personal_task_without_device_id(self):
        """Personal task without device_id"""
        task = ScheduledTask(
            id="test-1",
            scope=TaskScope.PERSONAL,  # Personal task
            type=TaskType.GREETING,
            name="テスト",
            time="08:00",
            message="テストメッセージ",
            schedule=SchedulePattern(type=ScheduleType.DAILY),
            device_id=None,  # No device_id
            active=True
        )
        
        assert task.validate() is False
    
    def test_validate_personal_task_with_device_id(self):
        """Personal task with device_id"""
        task = ScheduledTask(
            id="test-1",
            scope=TaskScope.PERSONAL,
            type=TaskType.GREETING, 
            name="テスト",
            time="08:00",
            message="テストメッセージ",
            schedule=SchedulePattern(type=ScheduleType.DAILY),
            device_id="device-123",  # With device_id
            active=True
        )
        
        assert task.validate() is True


class TestSchedulePattern:
    """Test class for SchedulePattern"""
    
    def test_validate_once_schedule_valid(self):
        """Valid one-time schedule"""
        pattern = SchedulePattern(
            type=ScheduleType.ONCE,
            target_datetime="2025-07-29T08:00:00"
        )
        
        assert pattern.validate() is True
    
    def test_validate_once_schedule_invalid(self):
        """Invalid one-time schedule (no target_datetime)"""
        pattern = SchedulePattern(
            type=ScheduleType.ONCE
        )
        
        assert pattern.validate() is False
    
    def test_validate_daily_schedule(self):
        """Daily schedule (always valid)"""
        pattern = SchedulePattern(
            type=ScheduleType.DAILY
        )
        
        assert pattern.validate() is True
    
    def test_validate_weekly_schedule_valid(self):
        """Valid weekly schedule"""
        pattern = SchedulePattern(
            type=ScheduleType.WEEKLY,
            days_of_week=["MONDAY", "FRIDAY"]
        )
        
        assert pattern.validate() is True
    
    def test_validate_weekly_schedule_invalid(self):
        """Invalid weekly schedule (no days_of_week)"""
        pattern = SchedulePattern(
            type=ScheduleType.WEEKLY
        )
        
        assert pattern.validate() is False