"""
Proactive Service - Dynamic task scheduling service

New proactive functionality implementation based on design documents.
Supports individual customization, dynamic task management, and LLM-integrated notifications.
Task Scheduler Service implementation following Clean Architecture.

# TODO: Phase 2~3 not yet implemented (see docs/phase2/2-2-4_proactive_features_design.md)
# Phase 2: Module Twin integration, cloud configuration sync, management UI integration
# Phase 3: AI condition judgment, automatic time adjustment, advanced scheduling (INTERVAL/MONTHLY/CONDITIONAL)
"""
import asyncio
import logging
import threading
import time
import queue
import json
import os
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Protocol
from dataclasses import dataclass, asdict
from enum import Enum
from zoneinfo import ZoneInfo


class TaskScope(Enum):
    COMMON = "common"        # Facility-wide (for all users)
    PERSONAL = "personal"    # Personal use only


class TaskExecutionStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ANNOUNCED = "announced"
    ANNOUNCEMENT_FAILED = "announcement_failed"
    
    # TODO: Future implementation planned (user response functionality)
    # Feature needed to detect user responses via voice recognition or management UI
    # - Voice recognition: positive responses like "yes", "understood", etc.
    # - Management UI: manual confirmation by caregivers
    # - Timeout setting: transition to NO_USER_RESPONSE after X minutes
    USER_ACKNOWLEDGED = "user_acknowledged"
    NO_USER_RESPONSE = "no_user_response"


@dataclass
class TaskStatusRecord:
    status: TaskExecutionStatus
    queued_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class TaskType(Enum):
    MEDICATION = "medication"
    MEDICAL_APPOINTMENT = "medical_appointment"
    LIFESTYLE = "lifestyle"
    PERSONAL_TASK = "personal_task"
    GREETING = "greeting"
    SOCIAL = "social"
    OTHER = "other"


class ScheduleType(Enum):
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CONDITIONAL = "conditional"


@dataclass
class SchedulePattern:
    type: ScheduleType
    
    # For one-time execution
    target_datetime: Optional[str] = None  # ISO format
    
    # For interval repeat
    interval_minutes: Optional[int] = None  # Every 2 hours = 120
    start_time: Optional[str] = None        # "09:00"
    end_time: Optional[str] = None          # "21:00"
    
    # For daily/weekly
    days_of_week: Optional[List[str]] = None  # ["MONDAY", "TUESDAY"]
    
    # For monthly
    day_of_month: Optional[int] = None      # 15th of every month
    week_of_month: Optional[int] = None     # 2nd week
    weekday_of_month: Optional[str] = None  # "FRIDAY"
    
    # Common settings
    start_date: Optional[str] = None        # "2025-07-26"
    end_date: Optional[str] = None          # "2025-08-26"
    max_occurrences: Optional[int] = None   # Maximum execution count
    
    # For conditional
    conditions: Optional[List[str]] = None  # ["sunny_weather"]
    
    def validate(self) -> bool:
        if self.type == ScheduleType.ONCE:
            return self.target_datetime is not None
        elif self.type == ScheduleType.INTERVAL:
            return (self.interval_minutes is not None and 
                   self.interval_minutes > 0)
        elif self.type == ScheduleType.DAILY:
            return True  # Basically valid with time only, no need to specify dates
        elif self.type == ScheduleType.WEEKLY:
            return (self.days_of_week is not None and 
                   len(self.days_of_week) > 0)
        elif self.type == ScheduleType.MONTHLY:
            return (self.day_of_month is not None or 
                   (self.week_of_month is not None and self.weekday_of_month is not None))
        return True


@dataclass
class ScheduledTask:
    id: str
    scope: TaskScope
    type: TaskType
    name: str
    time: str                   # "08:30" format (default: JST)
    message: str
    schedule: SchedulePattern
    device_id: Optional[str] = None  # Target device for personal tasks (corresponds to deviceId in CosmosDB)
    active: bool = True
    created_by: str = "manual"  # TODO: Implement creation source tracking and access control
    # manual, ai_conversation, ui
    
    def validate(self) -> bool:
        is_valid = (
            self.id and 
            self.name and 
            self.time and 
            self.message and
            self.schedule.validate()
        )
        
        if self.scope == TaskScope.PERSONAL:
            is_valid = is_valid and self.device_id is not None
            
        return is_valid


class TaskRepository(Protocol):
    
    def save_task(self, task: ScheduledTask) -> None:
        ...
    
    def load_tasks(self) -> List[ScheduledTask]:
        ...
    
    def delete_task(self, task_id: str) -> None:
        ...


class JsonTaskRepository:
    
    def __init__(self, file_path: str = "proactive_tasks.json"):
        self._file_path = file_path
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
    
    def load_tasks(self) -> List[ScheduledTask]:
        if not os.path.exists(self._file_path):
            return []
        
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tasks = []
                for task_data in data:
                    try:
                        # TODO: Improve hardcoded Enum conversion (maintainability when adding new Enum fields)
                        # Restore Enum values
                        task_data['scope'] = TaskScope(task_data['scope'])
                        task_data['type'] = TaskType(task_data['type'])
                        
                        # Restore SchedulePattern
                        schedule_data = task_data['schedule']
                        schedule_data['type'] = ScheduleType(schedule_data['type'])
                        task_data['schedule'] = SchedulePattern(**schedule_data)
                        
                        tasks.append(ScheduledTask(**task_data))
                    except (ValueError, KeyError, TypeError) as e:
                        self._logger.warning(f"Skipping invalid task data: {task_data}, error: {e}")
                        continue
                return tasks
        except Exception as e:
            self._logger.error(f"Failed to load tasks: {e}")
            return []
    
    def _write_tasks(self, tasks: List[ScheduledTask]) -> None:
        """Save task list to JSON file"""
        try:
            # Convert dataclass to dictionary (also stringify Enums)
            # TODO: Improve hardcoded Enum conversion (maintainability when adding new Enum fields)
            tasks_data = []
            for task in tasks:
                task_dict = asdict(task)
                task_dict['scope'] = task.scope.value
                task_dict['type'] = task.type.value
                task_dict['schedule']['type'] = task.schedule.type.value
                tasks_data.append(task_dict)
            
            with open(self._file_path, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._logger.error(f"Failed to write tasks: {e}")


class TaskSchedulerService:
    """Dynamic task scheduling service"""
    
    def __init__(self, 
                 task_repository: TaskRepository,
                 audio_output,
                 conversation_service=None,  # For LLM integration
                 config_loader=None):
        self._task_repository = task_repository
        self._audio_output = audio_output
        self._conversation_service = conversation_service
        self.config_loader = config_loader
        self._logger = logging.getLogger(__name__)
        self._active_tasks: List[ScheduledTask] = []
        self._running = False
    
    def add_task(self, task_config: dict) -> str:
        """
        Add a new task
        
        Args:
            task_config: Task configuration dictionary
                - time: "HH:MM" format (treated as JST if no timezone specified)
                - start_date: "YYYY-MM-DD" format (treated as JST if no timezone specified)
                - end_date: "YYYY-MM-DD" format (treated as JST if no timezone specified)
        
        Returns:
            ID of the added task
            
        Note:
            Assumes use within Japan, and treats date/time without timezone info as JST.
        """
        if 'id' not in task_config:
            task_config['id'] = str(uuid.uuid4())
        
        if isinstance(task_config.get('scope'), str):
            task_config['scope'] = TaskScope(task_config['scope'])
        if isinstance(task_config.get('type'), str):
            task_config['type'] = TaskType(task_config['type'])
        
        if isinstance(task_config.get('schedule'), dict):
            schedule_data = task_config['schedule'].copy()
            if isinstance(schedule_data.get('type'), str):
                schedule_data['type'] = ScheduleType(schedule_data['type'])
            task_config['schedule'] = SchedulePattern(**schedule_data)
        
        task = ScheduledTask(**task_config)
        if not task.validate():
            raise ValueError("Invalid task configuration")
            
        tasks = self._task_repository.load_tasks()
        updated = False
        for i, existing_task in enumerate(tasks):
            if existing_task.id == task.id:
                tasks[i] = task
                updated = True
                break
        
        if not updated:
            tasks.append(task)
        
        self._task_repository._write_tasks(tasks)
        self._reload_tasks()
        self._logger.info(f"Task added: {task.name} (scope: {task.scope.value})")
        return task.id
    
    def update_task(self, task_id: str, updates: dict) -> None:
        tasks = self._task_repository.load_tasks()
        for task in tasks:
            if task.id == task_id:
                updates_converted = updates.copy()
                
                if 'scope' in updates_converted and isinstance(updates_converted['scope'], str):
                    updates_converted['scope'] = TaskScope(updates_converted['scope'])
                
                if 'type' in updates_converted and isinstance(updates_converted['type'], str):
                    updates_converted['type'] = TaskType(updates_converted['type'])
                
                if 'schedule' in updates_converted and isinstance(updates_converted['schedule'], dict):
                    schedule_data = updates_converted['schedule'].copy()
                    if isinstance(schedule_data.get('type'), str):
                        schedule_data['type'] = ScheduleType(schedule_data['type'])
                    updates_converted['schedule'] = SchedulePattern(**schedule_data)
                
                for key, value in updates_converted.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                
                if not task.validate():
                    raise ValueError(f"Invalid task configuration after update: {task_id}")
                
                self._task_repository._write_tasks(tasks)
                self._reload_tasks()
                self._logger.info(f"Task updated: {task_id}")
                return
        raise ValueError(f"Task not found: {task_id}")
    
    def remove_task(self, task_id: str) -> None:
        tasks = self._task_repository.load_tasks()
        tasks = [task for task in tasks if task.id != task_id]
        self._task_repository._write_tasks(tasks)
        self._reload_tasks()
        self._logger.info(f"Task removed: {task_id}")
    
    def get_tasks_for_time(self, current_time: datetime, 
                          task_status_today: Dict[str, TaskStatusRecord], 
                          device_id: Optional[str] = None) -> List[ScheduledTask]:
        matching_tasks = []
        
        for task in self._active_tasks:
            if self._should_execute_task(task, current_time, task_status_today, device_id):
                matching_tasks.append(task)
        
        return matching_tasks
    
    def create_unified_message(self, tasks: List[ScheduledTask]) -> str:
        if len(tasks) == 1:
            return tasks[0].message  # Single task uses template
        
        if not self._conversation_service:
            return self._create_fallback_message(tasks)
        
        prompt = self._build_smart_unification_prompt(tasks)
        
        try:
            unified_message = self._conversation_service.generate_response(prompt)
            self._logger.info(f"Generated unified message for {len(tasks)} concurrent tasks")
            return unified_message
        except Exception as e:
            self._logger.error(f"Failed to generate unified message: {e}")
            # Fallback: simple concatenation
            return self._create_fallback_message(tasks)
    
    def start(self) -> None:
        self._reload_tasks()
        self._running = True
        self._logger.info("Task scheduler started")
    
    def stop(self) -> None:
        self._running = False
        self._logger.info("Task scheduler stopped")
    
    def _should_execute_task(self, task: ScheduledTask, current_time: datetime, 
                           task_status_today: Dict[str, TaskStatusRecord], device_id: Optional[str]) -> bool:
        if not task.active:
            return False
        
        if task.scope == TaskScope.PERSONAL and task.device_id != device_id:
            return False
        
        task_status = task_status_today.get(task.id)
        if task_status and task_status.status in (TaskExecutionStatus.ANNOUNCED, TaskExecutionStatus.QUEUED):
            return False
        
        # TODO: Future implementation - consider user response status
        # No re-execution needed for USER_ACKNOWLEDGED, re-announcement possible for NO_USER_RESPONSE
        # Example: if task_status and task_status.status == TaskExecutionStatus.USER_ACKNOWLEDGED:
        
        if not self._is_time_match(task, current_time):
            return False
        
        return self._is_schedule_match(task, current_time)
    
    def _is_time_match(self, task: ScheduledTask, current_time: datetime) -> bool:
        """Time matching (±1 minute range)"""
        try:
            # Use strptime for more robust time parsing
            task_time = datetime.strptime(task.time, "%H:%M").time()
            
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            
            current_local = current_time.astimezone(ZoneInfo("Asia/Tokyo"))
            current_minutes = current_local.hour * 60 + current_local.minute
            task_minutes = task_time.hour * 60 + task_time.minute
            
            return abs(current_minutes - task_minutes) <= 1
        except ValueError as e:
            self._logger.error(f"Invalid time format in task {task.id}: {task.time}, error: {e}")
            return False
    
    def _is_schedule_match(self, task: ScheduledTask, current_time: datetime) -> bool:
        schedule = task.schedule
        current_utc = self._normalize_to_utc(current_time)
        
        if schedule.type == ScheduleType.ONCE:
            return self._match_once_schedule(schedule, current_utc)
        elif schedule.type == ScheduleType.DAILY:
            return self._match_daily_schedule(schedule, current_utc)
        elif schedule.type == ScheduleType.WEEKLY:
            return self._match_weekly_schedule(schedule, current_utc)
        elif schedule.type == ScheduleType.INTERVAL:
            raise NotImplementedError(f"INTERVAL schedule type is not yet implemented")
        elif schedule.type == ScheduleType.MONTHLY:
            raise NotImplementedError(f"MONTHLY schedule type is not yet implemented")
        elif schedule.type == ScheduleType.CONDITIONAL:
            raise NotImplementedError(f"CONDITIONAL schedule type is not yet implemented")
        else:
            raise ValueError(f"Unknown schedule type: {schedule.type}")
    
    def _is_within_date_range(self, current_jst_date: date, schedule: SchedulePattern) -> bool:
        """
        Date range check (start_date, end_date)
        
        Args:
            current_jst_date: Current date in JST
            schedule: Schedule pattern
            
        Returns:
            True if within date range
        """
        if schedule.start_date:
            start_date = self._parse_date_safe(schedule.start_date, "start_date")
            if not start_date or current_jst_date < start_date:
                return False
        
        if schedule.end_date:
            end_date = self._parse_date_safe(schedule.end_date, "end_date")
            if not end_date or current_jst_date > end_date:
                return False
        
        return True
    
    def _parse_date_safe(self, date_str: str, field_name: str) -> Optional[date]:
        try:
            return datetime.fromisoformat(date_str).date()
        except ValueError:
            self._logger.error(f"Invalid {field_name} format: {date_str}")
            return None
    
    def _normalize_to_utc(self, current_time: datetime) -> datetime:
        if current_time.tzinfo is None:
            # Treat as local if no timezone information
            local_tz = ZoneInfo("Asia/Tokyo")
            current_time = current_time.replace(tzinfo=local_tz)
        
        return current_time.astimezone(ZoneInfo("UTC"))
    
    def _match_once_schedule(self, schedule: SchedulePattern, current_utc: datetime) -> bool:
        if not schedule.target_datetime:
            return False
        try:
            target_dt = datetime.fromisoformat(schedule.target_datetime)
            if target_dt.tzinfo is None:
                target_dt = target_dt.replace(tzinfo=ZoneInfo("Asia/Tokyo"))
            target_utc = target_dt.astimezone(ZoneInfo("UTC"))
            
            time_diff = abs((current_utc - target_utc).total_seconds())
            return time_diff <= 60
        except (ValueError, TypeError) as e:
            self._logger.error(f"Invalid target_datetime format: {schedule.target_datetime}, error: {e}")
            return False
    
    def _match_daily_schedule(self, schedule: SchedulePattern, current_utc: datetime) -> bool:
        current_jst = current_utc.astimezone(ZoneInfo("Asia/Tokyo"))
        current_date = current_jst.date()
        return self._is_within_date_range(current_date, schedule)
    
    def _match_weekly_schedule(self, schedule: SchedulePattern, current_utc: datetime) -> bool:
        current_jst = current_utc.astimezone(ZoneInfo("Asia/Tokyo"))
        current_weekday = current_jst.strftime('%a').upper()
        weekday_map = {
            'MON': 'MONDAY', 'TUE': 'TUESDAY', 'WED': 'WEDNESDAY',
            'THU': 'THURSDAY', 'FRI': 'FRIDAY', 'SAT': 'SATURDAY', 'SUN': 'SUNDAY'
        }
        current_day = weekday_map.get(current_weekday, '')
        
        if schedule.days_of_week and current_day in schedule.days_of_week:
            current_date = current_jst.date()
            return self._is_within_date_range(current_date, schedule)
        return False
    
    def _build_smart_unification_prompt(self, tasks: List[ScheduledTask]) -> str:
        task_list = []
        for task in tasks:
            scope_info = "for all" if task.scope == TaskScope.COMMON else "personal"
            task_list.append(f"- {task.name}（{task.type.value}・{scope_info}）: {task.message}")
        
        return f'''以下のリマインドが同時刻に設定されています。
適切な優先順序を判断して、1つの自然な案内メッセージにまとめてください。

タスク一覧:
{chr(10).join(task_list)}

優先度判断基準:
- 医療関連（服薬、診察、検査）は高優先度
- 緊急性や所要時間を考慮
- 論理的な実行順序（例：服薬→食事→診察→散歩）
- 個人向けタスクは全員向けより優先

要件:
- 高齢者にも分かりやすい自然な日本語
- 1つのメッセージで完結させる
- 150文字以内
- 「まず〜、その後〜」などの順序表現を使用

例: "15時になりました。まず薬をお飲みください。その後お食事をとって、診察の準備をお願いします。"'''
    
    def _create_fallback_message(self, tasks: List[ScheduledTask]) -> str:
        messages = [task.message for task in tasks]
        if len(tasks) <= 3:
            return f"複数の予定があります。{' '.join(messages)}"
        else:
            return f"複数の予定があります。少し長くなりますが、順番に読み上げます。{' '.join(messages)}"
    
    def _reload_tasks(self) -> None:
        self._active_tasks = [
            task for task in self._task_repository.load_tasks()
            if task.active
        ]
        self._logger.debug(f"Reloaded {len(self._active_tasks)} active tasks")
    
    @property
    def is_running(self) -> bool:
        return self._running


class TaskScheduler:
    """Audio queue-compatible task scheduler (main scheduler)"""
    
    def __init__(self, 
                 task_scheduler_service: TaskSchedulerService,
                 audio_output,  # Receive audio output directly
                 check_interval: int = 10,
                 queue_log_file: str = "task_executions.json",
                 max_queue_size: int = 50):
        self._task_scheduler_service = task_scheduler_service
        self._audio_output = audio_output
        self._check_interval = check_interval
        self._logger = logging.getLogger(__name__)
        
        # Thread-related
        self._running = False
        self._stop_event = threading.Event()  # For stop control
        self._scheduler_thread = None  # Initialize on start()
        self._audio_thread = None      # Initialize on start()
        
        # Audio output queue (with maximum size limit)
        self._audio_queue = queue.Queue(maxsize=max_queue_size)
        
        # Task execution status recording (for system restart support and duplicate prevention)
        self._queue_log_file = queue_log_file
        self._task_status_today = self._load_queue_log()
        self._queue_lock = threading.Lock()
    
    def start(self) -> None:
        if self._running:
            self._logger.warning("Task scheduler is already running")
            return
        self._running = True
        
        # Start audio worker and scheduler
        self._audio_thread = self._start_thread(self._audio_worker)
        self._scheduler_thread = self._start_thread(self._run)
        self._logger.info("Task scheduler started")
    
    def _start_thread(self, target):
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread
    
    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            if self._scheduler_thread.is_alive():
                self._logger.warning("Scheduler thread did not stop within timeout")
        
        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5)
            if self._audio_thread.is_alive():
                self._logger.warning("Audio thread did not stop within timeout")
        
        self._logger.info("Task scheduler stopped")
    
    def _run(self) -> None:
        while self._running:
            try:
                current_time = datetime.now(ZoneInfo("Asia/Tokyo"))
                
                # TODO: Consider implementing continuity assurance for system time changes and daylight saving transitions
                # - Time jump detection functionality (equivalent to _validate_time_consistency)
                # - Safe mode (stop new executions) and existing record preservation mechanism
                # - Administrator notification and manual recovery functionality
                # Currently not implemented (following YAGNI principle, will address when actual problems occur)
                
                self._check_and_queue_tasks(current_time)
                
            except Exception as e:
                self._logger.error(f"Scheduler main loop error: {e}", exc_info=True)
            
            time.sleep(self._check_interval)
    
    def _check_and_queue_tasks(self, current_time: datetime) -> None:
        with self._queue_lock:
            tasks_to_execute = self._task_scheduler_service.get_tasks_for_time(
                current_time, self._task_status_today
            )
            
            if not tasks_to_execute:
                return
            
            if self._try_add_to_queue(tasks_to_execute, current_time):
                return
            
            self._handle_full_queue(tasks_to_execute, current_time)
    
    def _try_add_to_queue(self, tasks_to_execute: List[ScheduledTask], current_time: datetime) -> bool:
        try:
            self._add_tasks_to_queue(tasks_to_execute, current_time)
            self._logger.debug(f"Queued {len(tasks_to_execute)} tasks for execution")
            return True
        except queue.Full:
            return False
    
    def _add_tasks_to_queue(self, tasks_to_execute: List[ScheduledTask], current_time: datetime) -> None:
        self._audio_queue.put({
            'tasks': tasks_to_execute,
            'timestamp': current_time
        }, timeout=1)
        
        # Record as queued (duplicate prevention)
        queued_timestamp = current_time.isoformat()
        for task in tasks_to_execute:
            self._task_status_today[task.id] = TaskStatusRecord(
                status=TaskExecutionStatus.QUEUED,
                queued_at=queued_timestamp
            )
        
        self._save_queue_log()
    
    def _handle_full_queue(self, tasks_to_execute: List[ScheduledTask], current_time: datetime) -> None:
        """Full queue handling: discard old tasks and prioritize new tasks"""
        try:
            old_item = self._audio_queue.get_nowait()
            old_task_names = [task.name for task in old_item['tasks']]
            
            self._add_tasks_to_queue(tasks_to_execute, current_time)
            
            task_names = [task.name for task in tasks_to_execute]
            self._logger.warning(f"Queue full: dropped old tasks {old_task_names}, added new tasks {task_names}")
            
        except queue.Empty:
            # Theoretically shouldn't happen, but just in case
            task_names = [task.name for task in tasks_to_execute]
            self._logger.error(f"Queue reported full but was empty, dropping new tasks: {task_names}")
    
    def _audio_worker(self) -> None:
        """Audio output worker - process sequentially from queue"""
        self._logger.info("Audio worker started")
        
        while not self._stop_event.is_set():
            try:
                task_group = self._audio_queue.get(timeout=1)
            except queue.Empty:
                continue
            
            try:
                self._process_queued_tasks(task_group)
                
            except Exception as e:
                self._logger.error(f"Unexpected audio worker error: {e}", exc_info=True)
                # Continue loop as continuity is important in elderly care systems
                # However, wait briefly to avoid consecutive errors
                time.sleep(0.1)
            finally:
                # Always call for success, failure, and stop signals
                try:
                    self._audio_queue.task_done()
                except ValueError:
                    pass  # Ignore if task_done() called too many times
        
        self._logger.info("Audio worker stopped")
    
    def _process_queued_tasks(self, task_group: dict) -> None:
        """Process queued task group (unified message generation, audio output, status update)"""
        tasks = task_group['tasks']
        
        unified_message = self._task_scheduler_service.create_unified_message(tasks)
        
        try:
            # Run async method in sync context using asyncio.run()
            # This creates a new event loop for each call, which is fine for announcements
            asyncio.run(self._audio_output.speech_announcement(unified_message))
            status = TaskExecutionStatus.ANNOUNCED
            error_msg = None
            
            # Record ProactiveService utterances in ConversationService (memory storage)
            try:
                if self._task_scheduler_service._conversation_service:
                    self._task_scheduler_service._conversation_service._record_and_send_utterance("assistant", unified_message)
            except Exception as memory_error:
                self._logger.warning(f"Memory recording failed (non-critical): {memory_error}")
            
            task_names = [task.name for task in tasks]
            self._logger.info(
                f"Tasks announced: {task_names}, "
                f"message: {unified_message[:100]}{'...' if len(unified_message) > 100 else ''}"
            )
            
        except Exception as audio_error:
            status = TaskExecutionStatus.ANNOUNCEMENT_FAILED
            error_msg = str(audio_error)
            
            # TTS failure is a recoverable error at WARNING level
            task_ids = [task.id for task in tasks]
            self._logger.warning(f"TTS failed for tasks {task_ids}: {audio_error}")
        
        task_ids = [task.id for task in tasks]
        self._update_task_status(task_ids, status, error_msg)
    
    def _load_queue_log(self) -> Dict[str, TaskStatusRecord]:
        """Load task execution status from file (for system restart support)"""
        if not os.path.exists(self._queue_log_file):
            return {}
        
        try:
            with open(self._queue_log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
            result = {}
            
            for task_id, status_data in data.items():
                if not isinstance(status_data, dict):
                    continue
                
                queued_at = status_data.get('queued_at', '')
                if not queued_at.startswith(today):
                    continue
                
                result[task_id] = TaskStatusRecord(
                    status=TaskExecutionStatus(status_data.get('status', 'queued')),
                    queued_at=queued_at,
                    completed_at=status_data.get('completed_at'),
                    error_message=status_data.get('error_message')
                )
            
            return result
        except (json.JSONDecodeError, Exception) as e:
            self._logger.error(f"Failed to load queue log: {e}")
            return {}
    
    def _save_queue_log(self) -> None:
        try:
            save_data = {}
            for task_id, status_record in self._task_status_today.items():
                record_dict = asdict(status_record)
                record_dict['status'] = status_record.status.value
                save_data[task_id] = record_dict
            
            with open(self._queue_log_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._logger.error(f"Failed to save queue log: {e}")    
    
    def _update_task_status(self, task_ids: List[str], status: TaskExecutionStatus, error_message: Optional[str] = None) -> None:
        with self._queue_lock:
            current_time = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()
            
            for task_id in task_ids:
                if task_id not in self._task_status_today:
                    continue
                
                status_record = self._task_status_today[task_id]
                status_record.status = status
                
                if status == TaskExecutionStatus.ANNOUNCED:
                    status_record.completed_at = current_time
                elif status == TaskExecutionStatus.ANNOUNCEMENT_FAILED:
                    status_record.error_message = error_message
                
                # TODO: 将来実装 - ユーザー応答状態の処理
                # elif status == TaskExecutionStatus.USER_ACKNOWLEDGED:
                #     status_record.acknowledged_at = current_time
                # elif status == TaskExecutionStatus.NO_USER_RESPONSE:
                #     status_record.timeout_at = current_time
            
            self._save_queue_log()
    
    
    @property
    def is_running(self) -> bool:
        return self._running


class ProactiveServiceError(Exception):
    pass


class ProactiveService:
    """
    New proactive service
    
    Supports dynamic task management following Clean Architecture.
    Provides new functionality while maintaining compatibility with existing APIs.
    """
    
    def __init__(self, audio_output, config_loader) -> None:
        """Initialize ProactiveService with Clean Architecture compliance
        
        Args:
            audio_output: Audio output adapter for TTS
            config_loader: ConfigLoader instance for dynamic configuration access
        """
        self._logger = logging.getLogger(__name__)
        self.config_loader = config_loader
        
        # Data file path configuration from ConfigLoader
        task_file = self.config_loader.get("proactive_data.task_file")
        queue_log_file = self.config_loader.get("proactive_data.queue_log_file")
        
        # Infrastructure layer initialization
        self._task_repository = JsonTaskRepository(task_file)
        
        # Application layer initialization
        self._task_scheduler_service = TaskSchedulerService(
            task_repository=self._task_repository,
            audio_output=audio_output,
            conversation_service=None,
            config_loader=self.config_loader
        )
        
        # Scheduler initialization
        self._scheduler = TaskScheduler(
            task_scheduler_service=self._task_scheduler_service,
            audio_output=audio_output,
            check_interval=self.config_loader.get("proactive_data.check_interval"),
            queue_log_file=queue_log_file,
            max_queue_size=self.config_loader.get("proactive_data.max_queue_size")
        )
        
        
        self._logger.info("ProactiveService initialized with new task scheduler")
    
    def start(self) -> None:
        try:
            self._task_scheduler_service.start()
            self._scheduler.start()
            self._logger.info("Proactive service started successfully")
        except Exception as e:
            error_msg = f"Failed to start proactive service: {e}"
            self._logger.error(error_msg)
            raise ProactiveServiceError(error_msg) from e
    
    def stop(self) -> None:
        try:
            self._scheduler.stop()
            self._task_scheduler_service.stop()
            self._logger.info("Proactive service stopped successfully")
        except Exception as e:
            error_msg = f"Error stopping proactive service: {e}"
            self._logger.error(error_msg)
            raise ProactiveServiceError(error_msg) from e
    
    def add_task(self, task_config: dict) -> str:
        return self._task_scheduler_service.add_task(task_config)
    
    def update_task(self, task_id: str, updates: dict) -> None:
        self._task_scheduler_service.update_task(task_id, updates)
    
    def remove_task(self, task_id: str) -> None:
        self._task_scheduler_service.remove_task(task_id)
    
    def set_conversation_service(self, conversation_service) -> None:
        self._task_scheduler_service._conversation_service = conversation_service
        self._logger.info("Conversation service connected for LLM integration")
    
    @property
    def is_running(self) -> bool:
        return self._scheduler.is_running
    
