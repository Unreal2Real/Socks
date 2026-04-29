import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable
from .config import CourseConfig, Settings

logger = logging.getLogger(__name__)


class RecordTask:
    def __init__(
        self,
        course: CourseConfig,
        callback: Callable,
        task_id: Optional[str] = None,
    ):
        self.course = course
        self.callback = callback
        self.task_id = task_id or f"{course.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None

    def should_run_now(self) -> bool:
        if not self.course.enabled:
            return False
        if not self.course.schedule_time:
            return False

        now = datetime.now()
        weekday = now.weekday()

        if weekday not in self.course.days_of_week:
            return False

        if self.last_run and (now - self.last_run) < timedelta(hours=1):
            return False

        try:
            target_hour, target_minute = map(int, self.course.schedule_time.split(":"))
            if now.hour == target_hour and now.minute == target_minute:
                return True
        except (ValueError, TypeError):
            pass

        return False

    def mark_run(self):
        self.last_run = datetime.now()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "course_name": self.course.name,
            "schedule_time": self.course.schedule_time,
            "days_of_week": self.course.days_of_week,
            "enabled": self.course.enabled,
        }


class Scheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._tasks: list[RecordTask] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_task(self, task: RecordTask):
        self._tasks.append(task)
        logger.info(f"已添加定时任务: {task.course.name} @ {task.course.schedule_time}")

    def remove_task(self, course_name: str) -> bool:
        for i, task in enumerate(self._tasks):
            if task.course.name == course_name:
                self._tasks.pop(i)
                logger.info(f"已移除定时任务: {course_name}")
                return True
        return False

    def get_tasks(self) -> list[RecordTask]:
        return list(self._tasks)

    def start(self):
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"调度器已启动，共 {len(self._tasks)} 个定时任务")

    def stop(self):
        self._running = False
        logger.info("调度器已停止")

    def _run_loop(self):
        while self._running:
            now = datetime.now()
            for task in self._tasks:
                if task.should_run_now():
                    logger.info(f"触发定时录制: {task.course.name}")
                    try:
                        task.callback(task.course)
                        task.mark_run()
                    except Exception as e:
                        logger.error(f"定时录制失败 [{task.course.name}]: {e}")

            time.sleep(self.settings.check_interval)

    def sync_from_courses(self, callback: Callable):
        self._tasks.clear()
        for course in self.settings.courses:
            if course.schedule_time and course.enabled:
                self.add_task(RecordTask(course, callback))
