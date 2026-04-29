import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class RecordingRecord:
    def __init__(
        self,
        course_name: str,
        file_path: str,
        duration: float = 0,
        file_size: int = 0,
        url: str = "",
        status: str = "completed",
        created_at: Optional[str] = None,
        record_id: Optional[str] = None,
    ):
        self.course_name = course_name
        self.file_path = file_path
        self.duration = duration
        self.file_size = file_size
        self.url = url
        self.status = status
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.record_id = record_id or datetime.now().strftime("%Y%m%d%H%M%S")

    def to_dict(self) -> dict:
        return {
            "id": self.record_id,
            "course_name": self.course_name,
            "file_path": self.file_path,
            "duration": self.duration,
            "file_size": self.file_size,
            "url": self.url,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            course_name=d.get("course_name", ""),
            file_path=d.get("file_path", ""),
            duration=d.get("duration", 0),
            file_size=d.get("file_size", 0),
            url=d.get("url", ""),
            status=d.get("status", "completed"),
            created_at=d.get("created_at", ""),
            record_id=d.get("id", ""),
        )


class RecordingStorage:
    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.records_file = Path(settings.config_dir) / "recordings.json"
        self._records: List[RecordingRecord] = []
        self._load()

    def generate_output_path(self, course_name: str, url: str = "") -> str:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        safe_name = self._sanitize_filename(course_name)
        dir_path = os.path.join(self.settings.recordings_dir, safe_name, date_str)
        os.makedirs(dir_path, exist_ok=True)
        filename = f"{safe_name}_{date_str}_{time_str}.mp4"
        return os.path.join(dir_path, filename)

    def generate_audio_path(self, course_name: str, url: str = "") -> str:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        safe_name = self._sanitize_filename(course_name)
        dir_path = os.path.join(self.settings.recordings_dir, safe_name, date_str)
        os.makedirs(dir_path, exist_ok=True)
        filename = f"{safe_name}_{date_str}_{time_str}.aac"
        return os.path.join(dir_path, filename)

    def save_record(self, record: RecordingRecord):
        self._records.append(record)
        self._save()

    def update_record(self, record_id: str, **kwargs):
        for record in self._records:
            if record.record_id == record_id:
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                self._save()
                return True
        return False

    def get_records(self, course_name: Optional[str] = None, limit: int = 50) -> List[RecordingRecord]:
        records = self._records
        if course_name:
            records = [r for r in records if r.course_name == course_name]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def get_recent_record(self, course_name: str) -> Optional[RecordingRecord]:
        records = self.get_records(course_name, limit=1)
        return records[0] if records else None

    def delete_record(self, record_id: str) -> bool:
        for i, record in enumerate(self._records):
            if record.record_id == record_id:
                path = record.file_path
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError as e:
                        logger.warning(f"删除文件失败: {e}")
                self._records.pop(i)
                self._save()
                return True
        return False

    def get_total_size(self) -> int:
        return sum(r.file_size for r in self._records)

    def get_course_stats(self) -> dict:
        stats = {}
        for r in self._records:
            if r.course_name not in stats:
                stats[r.course_name] = {
                    "count": 0,
                    "total_duration": 0,
                    "total_size": 0,
                }
            stats[r.course_name]["count"] += 1
            stats[r.course_name]["total_duration"] += r.duration
            stats[r.course_name]["total_size"] += r.file_size
        return stats

    def _load(self):
        if self.records_file.exists():
            try:
                raw = json.loads(self.records_file.read_text(encoding="utf-8"))
                self._records = [RecordingRecord.from_dict(item) for item in raw]
            except (json.JSONDecodeError, OSError):
                self._records = []

    def _save(self):
        self.records_file.write_text(
            json.dumps(
                [r.to_dict() for r in self._records],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        invalid_chars = r'\/:*?"<>|'
        for c in invalid_chars:
            name = name.replace(c, "_")
        return name.strip() or "未命名课程"
