import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


COOKIE_FILE = "xiaoetong_cookies.json"

DEFAULT_CONFIG = {
    "recordings_dir": str(Path.home() / "Videos" / "小鹅通课程"),
    "ffmpeg_path": "ffmpeg",
    "quality": "best",
    "frame_rate": 30,
    "audio_only": False,
    "headless": False,
    "show_browser": True,
    "auto_start": True,
    "cookie_file": COOKIE_FILE,
    "page_load_timeout": 60,
    "check_interval": 30,
    "schedule": [],
}


@dataclass
class CourseConfig:
    name: str
    url: str
    schedule_time: Optional[str] = None
    days_of_week: list = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    quality: str = "best"
    audio_only: bool = False
    enabled: bool = True

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


class Settings:
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = str(Path(__file__).parent / "config")
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "settings.json"
        self.courses_file = self.config_dir / "courses.json"
        self._data = {}
        self._courses = []
        self.load()

    @property
    def recordings_dir(self) -> str:
        return self._data.get("recordings_dir", DEFAULT_CONFIG["recordings_dir"])

    @recordings_dir.setter
    def recordings_dir(self, value: str):
        self._data["recordings_dir"] = value
        self.save()

    @property
    def ffmpeg_path(self) -> str:
        return self._data.get("ffmpeg_path", DEFAULT_CONFIG["ffmpeg_path"])

    @property
    def quality(self) -> str:
        return self._data.get("quality", DEFAULT_CONFIG["quality"])

    @property
    def frame_rate(self) -> int:
        return self._data.get("frame_rate", DEFAULT_CONFIG["frame_rate"])

    @property
    def audio_only(self) -> bool:
        return self._data.get("audio_only", DEFAULT_CONFIG["audio_only"])

    @property
    def headless(self) -> bool:
        return self._data.get("headless", DEFAULT_CONFIG["headless"])

    @property
    def show_browser(self) -> bool:
        return self._data.get("show_browser", DEFAULT_CONFIG["show_browser"])

    @property
    def auto_start(self) -> bool:
        return self._data.get("auto_start", DEFAULT_CONFIG["auto_start"])

    @property
    def cookie_file(self) -> str:
        return self._data.get("cookie_file", DEFAULT_CONFIG["cookie_file"])

    @property
    def page_load_timeout(self) -> int:
        return self._data.get("page_load_timeout", DEFAULT_CONFIG["page_load_timeout"])

    @property
    def check_interval(self) -> int:
        return self._data.get("check_interval", DEFAULT_CONFIG["check_interval"])

    @property
    def courses(self) -> list:
        return self._courses

    def get_cookie_path(self) -> str:
        return str(self.config_dir / self.cookie_file)

    def add_course(self, course: CourseConfig):
        self._courses.append(course)
        self._save_courses()

    def remove_course(self, name: str) -> bool:
        for i, c in enumerate(self._courses):
            if c.name == name:
                self._courses.pop(i)
                self._save_courses()
                return True
        return False

    def get_course(self, name: str) -> Optional[CourseConfig]:
        for c in self._courses:
            if c.name == name:
                return c
        return None

    def load(self):
        if self.config_file.exists():
            try:
                self._data = json.loads(self.config_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._load_courses()

    def save(self):
        self.config_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_courses(self):
        self._courses = []
        if self.courses_file.exists():
            try:
                raw = json.loads(self.courses_file.read_text(encoding="utf-8"))
                for item in raw:
                    self._courses.append(CourseConfig.from_dict(item))
            except (json.JSONDecodeError, OSError):
                pass

    def _save_courses(self):
        self.courses_file.write_text(
            json.dumps([c.to_dict() for c in self._courses], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
