import os
import sys
import time
import signal
import subprocess
import logging
import threading
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


IS_WINDOWS = sys.platform == "win32"


class Recorder:
    def __init__(self, settings: "Settings"):
        self.settings = settings
        self._process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[float] = None
        self._output_path: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0
        return time.time() - self._start_time

    @property
    def output_path(self) -> Optional[str]:
        return self._output_path

    def _get_display_input(self) -> str:
        system = sys.platform
        if system == "darwin":
            return "Capture screen 0"
        elif IS_WINDOWS:
            return "desktop"
        else:
            display = os.environ.get("DISPLAY", ":0")
            return display

    def _build_ffmpeg_cmd(
        self,
        output_path: str,
        audio_only: bool = False,
        quality: str = "best",
        frame_rate: int = 30,
    ) -> list:
        system = sys.platform
        ffmpeg = self.settings.ffmpeg_path

        if system == "darwin":
            if audio_only:
                return [
                    ffmpeg,
                    "-f", "avfoundation",
                    "-i", ":0",
                    "-acodec", "aac",
                    "-b:a", "192k",
                    "-y",
                    output_path,
                ]
            return self._build_macos_video_cmd(ffmpeg, output_path, quality, frame_rate)
        elif IS_WINDOWS:
            if audio_only:
                return [
                    ffmpeg, "-f", "dshow", "-i", "audio=virtual-audio-capturer",
                    "-acodec", "aac", "-b:a", "192k", "-y", output_path,
                ]
            return self._build_windows_video_cmd(ffmpeg, output_path, quality, frame_rate)
        else:
            display = os.environ.get("DISPLAY", ":0")
            if audio_only:
                return [
                    ffmpeg, "-f", "pulse", "-i", "default",
                    "-acodec", "aac", "-b:a", "192k", "-y", output_path,
                ]
            return self._build_linux_video_cmd(ffmpeg, output_path, quality, frame_rate, display)

    def _build_macos_video_cmd(
        self, ffmpeg: str, output_path: str, quality: str, frame_rate: int
    ) -> list:
        crf = self._quality_to_crf(quality)
        cmd = [
            ffmpeg,
            "-f", "avfoundation",
            "-capture_cursor", "1",
            "-capture_mouse_clicks", "1",
            "-video_device_index", "0",
            "-r", str(frame_rate),
            "-i", "1",
            "-f", "avfoundation",
            "-i", ":0",
            "-c:v", "h264_videotoolbox",
            "-q:v", str(crf),
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ]
        return cmd

    def _build_windows_video_cmd(
        self, ffmpeg: str, output_path: str, quality: str, frame_rate: int
    ) -> list:
        crf = self._quality_to_crf(quality)
        gdigrab_framerate = min(frame_rate, 30)

        cmd = [
            ffmpeg,
            "-f", "gdigrab",
            "-framerate", str(gdigrab_framerate),
            "-draw_mouse", "1",
            "-offset_x", "0",
            "-offset_y", "0",
            "-video_size", "desktop",
            "-i", "desktop",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ]
        return cmd

    def _build_windows_audio_cmd(self, ffmpeg: str, output_path: str) -> list:
        return [
            ffmpeg,
            "-f", "dshow",
            "-i", "audio=virtual-audio-capturer",
            "-acodec", "aac",
            "-b:a", "192k",
            "-y",
            output_path,
        ]

    def _build_linux_video_cmd(
        self, ffmpeg: str, output_path: str, quality: str, frame_rate: int, display: str
    ) -> list:
        crf = self._quality_to_crf(quality)
        return [
            ffmpeg,
            "-f", "x11grab",
            "-framerate", str(frame_rate),
            "-s", "1920x1080",
            "-i", f"{display}.0+0,0",
            "-f", "pulse",
            "-i", "default",
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ]

    def _quality_to_crf(self, quality: str) -> int:
        mapping = {
            "best": 18,
            "high": 20,
            "medium": 23,
            "low": 28,
        }
        return mapping.get(quality, 23)

    def list_windows_audio_devices(self) -> list:
        if not IS_WINDOWS:
            return []
        try:
            result = subprocess.run(
                [self.settings.ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=10,
            )
            lines = (result.stderr or result.stdout or "").split("\n")
            devices = []
            for line in lines:
                if '"' in line and ("audio" in line.lower() or "Alternative" in line):
                    devices.append(line.strip())
            return devices
        except Exception as e:
            logger.warning(f"无法枚举音频设备: {e}")
            return []

    def list_windows_video_devices(self) -> list:
        if not IS_WINDOWS:
            return []
        try:
            result = subprocess.run(
                [self.settings.ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=10,
            )
            lines = (result.stderr or result.stdout or "").split("\n")
            devices = []
            for line in lines:
                if '"' in line and "video" in line.lower():
                    devices.append(line.strip())
            return devices
        except Exception as e:
            logger.warning(f"无法枚举视频设备: {e}")
            return []

    def start_recording(
        self,
        output_path: str,
        audio_only: bool = False,
        quality: str = "best",
        frame_rate: int = 30,
        use_ddagrab: bool = False,
    ) -> bool:
        if self.is_recording:
            logger.warning("已在录制中")
            return False

        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        if IS_WINDOWS and audio_only:
            cmd = self._build_windows_audio_cmd(self.settings.ffmpeg_path, output_path)
        else:
            cmd = self._build_ffmpeg_cmd(output_path, audio_only, quality, frame_rate)
        logger.info(f"开始录制: {output_path}")

        try:
            startupinfo = None
            if IS_WINDOWS:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
            )
            self._output_path = output_path
            self._start_time = time.time()
            self._stop_event.clear()

            time.sleep(2)
            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                logger.error(f"ffmpeg 启动失败: {stderr}")
                self._process = None
                return False

            logger.info("录制已开始")
            return True
        except FileNotFoundError:
            logger.error("未找到 ffmpeg，请确保已安装 ffmpeg 并添加到 PATH")
            return False
        except Exception as e:
            logger.error(f"启动录制失败: {e}")
            return False

    def stop_recording(self) -> Optional[str]:
        if not self.is_recording:
            logger.warning("没有正在进行的录制")
            return self._output_path

        logger.info("正在停止录制...")
        self._stop_event.set()

        try:
            if self._process:
                if IS_WINDOWS:
                    self._process.terminate()
                else:
                    self._process.send_signal(signal.SIGINT)
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("ffmpeg 未响应，发送 SIGTERM")
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        logger.warning("ffmpeg 未响应，强制终止")
                        self._process.kill()
                        self._process.wait()
        except Exception as e:
            logger.error(f"停止录制时出错: {e}")

        duration = time.time() - self._start_time if self._start_time else 0
        logger.info(f"录制已停止，时长: {int(duration)}秒，文件: {self._output_path}")

        result_path = self._output_path
        self._process = None
        self._output_path = None
        self._start_time = None

        return result_path

    def start_recording_async(
        self,
        output_path: str,
        audio_only: bool = False,
        quality: str = "best",
        frame_rate: int = 30,
        on_complete=None,
    ):
        def _run():
            self.start_recording(output_path, audio_only, quality, frame_rate)
            if self._process:
                self._process.wait()
            if on_complete:
                on_complete(self._output_path)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
