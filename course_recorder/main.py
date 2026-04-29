#!/usr/bin/env python3
import os
import sys
import time
import json
import signal
import logging
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from course_recorder.config import Settings, CourseConfig
from course_recorder.browser import CourseBrowser
from course_recorder.recorder import Recorder
from course_recorder.storage import RecordingStorage, RecordingRecord
from course_recorder.scheduler import Scheduler, RecordTask

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("course_recorder")


class CourseRecorderApp:
    def __init__(self):
        self.settings = Settings()
        self.storage = RecordingStorage(self.settings)
        self.browser = CourseBrowser(self.settings)
        self.recorder = Recorder(self.settings)
        self.scheduler = Scheduler(self.settings)
        self._running = False

    def start(self):
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info("接收到终止信号，正在清理...")
        if self.recorder.is_recording:
            self._finish_recording()
        self.browser.stop()
        self.scheduler.stop()
        self._running = False
        sys.exit(0)

    def cmd_login(self, args):
        logger.info("=" * 50)
        logger.info("小鹅通课程录制工具 - 登录")
        logger.info("=" * 50)
        logger.info("请在浏览器中手动登录小鹅通")
        logger.info("登录后 Cookie 会自动保存，下次无需重复登录")
        print()

        self.browser.start()
        success = self.browser.wait_for_login(timeout_seconds=300)
        if success:
            logger.info("登录成功！Cookie 已保存")
            logger.info(f"Cookie 文件: {self.settings.get_cookie_path()}")
        else:
            logger.error("登录失败或超时")
        self.browser.stop()

    def cmd_add(self, args):
        logger.info(f"添加课程: {args.name}")
        course = CourseConfig(
            name=args.name,
            url=args.url,
            schedule_time=args.time,
            audio_only=args.audio_only,
        )
        self.settings.add_course(course)
        logger.info(f"课程 '{args.name}' 已添加")
        logger.info(f"  URL: {args.url}")
        if args.time:
            logger.info(f"  定时录制: 每天 {args.time}")
        if args.audio_only:
            logger.info(f"  仅录制音频")

    def cmd_list(self, args):
        courses = self.settings.courses
        if not courses:
            logger.info("暂无已添加的课程")
            return

        logger.info(f"{'='*60}")
        logger.info(f"已添加的课程 (共 {len(courses)} 个)")
        logger.info(f"{'='*60}")
        for i, c in enumerate(courses, 1):
            logger.info(f"{i}. {c.name}")
            logger.info(f"   URL: {c.url}")
            if c.schedule_time:
                days = ["周一","周二","周三","周四","周五","周六","周日"]
                day_str = ",".join(days[d] for d in c.days_of_week) if c.days_of_week else "每天"
                logger.info(f"   定时: {c.schedule_time} ({day_str})")
            logger.info(f"   仅音频: {'是' if c.audio_only else '否'}")
            logger.info(f"   启用: {'是' if c.enabled else '否'}")
            print()

        logger.info(f"\n录制统计:")
        stats = self.storage.get_course_stats()
        for name, s in stats.items():
            hours = s["total_duration"] / 3600
            size_mb = s["total_size"] / (1024 * 1024)
            logger.info(f"  {name}: {s['count']}次录制, {hours:.1f}小时, {size_mb:.1f}MB")

    def cmd_remove(self, args):
        if self.settings.remove_course(args.name):
            logger.info(f"课程 '{args.name}' 已移除")
        else:
            logger.error(f"未找到课程 '{args.name}'")

    def cmd_record(self, args):
        course = self._resolve_course(args)
        if not course:
            return

        logger.info(f"开始录制课程: {course.name}")
        self.browser.start()

        if not self.browser.is_logged_in:
            logger.warning("未检测到登录 Cookie，请先运行 login 命令登录")

        try:
            self.browser.navigate(course.url)
            time.sleep(5)

            has_video = self.browser.detect_video_element(timeout=20)
            has_audio = self.browser.detect_audio_element(timeout=10)

            if not has_video and not has_audio:
                logger.warning("未检测到音视频播放元素")
                logger.info("请确认页面是否已加载完成")
                ans = input("是否继续录制? (y/n): ").strip().lower()
                if ans != "y":
                    logger.info("取消录制")
                    self.browser.stop()
                    return

            self.browser.try_play_video()
            time.sleep(2)

            if has_video:
                video_info = self.browser.get_video_info()
                logger.info(f"视频信息: {video_info}")

            logger.info("等待视频开始播放 (最长等待60秒)...")
            playback_started = self.browser.wait_for_playback_start(timeout=60)

            if not playback_started:
                logger.warning("未检测到视频播放，仍将继续录制画面")
                ans = input("未检测到播放进度变化，是否继续录制? (y/n): ").strip().lower()
                if ans != "y":
                    logger.info("取消录制")
                    self.browser.stop()
                    return

            page_title = self.browser.get_page_title()
            course_name = course.name or page_title or "未知课程"
            audio_only = course.audio_only or args.audio_only

            if audio_only:
                output_path = self.storage.generate_audio_path(course_name)
            else:
                output_path = self.storage.generate_output_path(course_name)

            logger.info(f"输出文件: {output_path}")

            record = RecordingRecord(
                course_name=course_name,
                file_path=output_path,
                url=course.url,
                status="recording",
            )
            self.storage.save_record(record)

            record_id = record.record_id
            success = self.recorder.start_recording(
                output_path=output_path,
                audio_only=audio_only,
                quality=self.settings.quality,
                frame_rate=self.settings.frame_rate,
            )

            if not success:
                logger.error("录制启动失败，请确保已安装 ffmpeg")
                self.storage.update_record(record_id, status="failed")
                self.browser.stop()
                return

            logger.info("录制中... 按 Ctrl+C 停止录制")
            logger.info(f"已录制: 0秒")

            last_log_time = time.time()
            try:
                while self.recorder.is_recording and self._running:
                    elapsed = self.recorder.elapsed_seconds
                    if time.time() - last_log_time >= 30:
                        logger.info(f"已录制: {int(elapsed)}秒")
                        last_log_time = time.time()
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("用户中断录制")

            result_path = self._finish_recording()

            if result_path and os.path.exists(result_path):
                file_size = os.path.getsize(result_path)
                duration = self.recorder.elapsed_seconds
                self.storage.update_record(
                    record_id,
                    status="completed",
                    duration=duration,
                    file_size=file_size,
                )
                logger.info(f"录制完成!")
                logger.info(f"  文件: {result_path}")
                logger.info(f"  时长: {int(duration)}秒 ({duration/60:.1f}分钟)")
                logger.info(f"  大小: {file_size/(1024*1024):.1f}MB")
            else:
                self.storage.update_record(record_id, status="failed")
                logger.error("录制失败，未生成输出文件")

        except KeyboardInterrupt:
            logger.info("用户中断")
            self._finish_recording()
        except Exception as e:
            logger.error(f"录制过程中出错: {e}", exc_info=True)
            self._finish_recording()
        finally:
            self.browser.stop()

    def _resolve_course(self, args) -> CourseConfig:
        if args.url:
            return CourseConfig(name=args.name or "临时录制", url=args.url)
        if args.name:
            course = self.settings.get_course(args.name)
            if course:
                return course
            logger.error(f"未找到已保存的课程 '{args.name}'，请先 add 添加或使用 --url 参数")
            return None
        logger.error("请提供课程名称 (--name) 或 URL (--url)")
        return None

    def _finish_recording(self) -> str:
        if self.recorder.is_recording:
            return self.recorder.stop_recording() or ""
        return ""

    def cmd_records(self, args):
        course_name = args.name
        records = self.storage.get_records(course_name)

        if not records:
            logger.info("暂无录制记录")
            return

        logger.info(f"{'='*70}")
        logger.info(f"录制记录 (共 {len(records)} 条)")
        logger.info(f"{'='*70}")

        for i, r in enumerate(records, 1):
            size_mb = r.file_size / (1024 * 1024)
            duration_min = r.duration / 60
            logger.info(f"{i}. {r.course_name}")
            logger.info(f"   时间: {r.created_at}")
            logger.info(f"   时长: {duration_min:.1f}分钟")
            logger.info(f"   大小: {size_mb:.1f}MB")
            logger.info(f"   状态: {r.status}")
            logger.info(f"   文件: {r.file_path}")
            print()

    def cmd_delete_record(self, args):
        if self.storage.delete_record(args.id):
            logger.info(f"记录 {args.id} 已删除")
        else:
            logger.error(f"未找到记录 {args.id}")

    def cmd_schedule(self, args):
        record_callback = self._get_schedule_callback()
        self.scheduler.sync_from_courses(record_callback)

        tasks = self.scheduler.get_tasks()
        if not tasks:
            logger.info("没有启用的定时录制任务")
            logger.info("请先使用 add 命令添加课程，并设置 --time 参数")
            return

        self.scheduler.start()
        logger.info(f"调度器已启动，共 {len(tasks)} 个定时任务")

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("用户中断调度器")
            self.scheduler.stop()

    def _get_schedule_callback(self):
        def callback(course: CourseConfig):
            logger.info(f"[定时任务] 开始录制: {course.name}")

            self.browser.start()
            if not self.browser.is_logged_in:
                logger.error("Cookie 已过期，无法录制")
                self.browser.stop()
                return

            try:
                self.browser.navigate(course.url)
                time.sleep(5)
                self.browser.detect_video_element(timeout=20)
                self.browser.try_play_video()
                self.browser.wait_for_playback_start(timeout=60)

                page_title = self.browser.get_page_title()
                course_name = course.name or page_title or "未知课程"
                audio_only = course.audio_only

                if audio_only:
                    output_path = self.storage.generate_audio_path(course_name)
                else:
                    output_path = self.storage.generate_output_path(course_name)

                record = RecordingRecord(
                    course_name=course_name,
                    file_path=output_path,
                    url=course.url,
                    status="recording",
                )
                self.storage.save_record(record)

                success = self.recorder.start_recording(
                    output_path=output_path,
                    audio_only=audio_only,
                    quality=self.settings.quality,
                )

                if success:
                    logger.info(f"[定时任务] 录制中: {course.name}")
                else:
                    logger.error(f"[定时任务] 录制启动失败: {course.name}")
            except Exception as e:
                logger.error(f"[定时任务] 录制异常: {e}")
            finally:
                self.browser.stop()

        return callback

    def cmd_devices(self, args):
        logger.info("检测系统录制设备...")
        if sys.platform == "win32":
            logger.info("\n--- 音频输入设备 ---")
            audio_devices = self.recorder.list_windows_audio_devices()
            if audio_devices:
                for d in audio_devices:
                    logger.info(f"  {d}")
            else:
                logger.info("  (未检测到音频设备，安装虚拟音频驱动可捕获系统声音)")
                logger.info("  推荐: https://vb-audio.com/Cable/")

            logger.info("\n--- 视频采集设备 ---")
            video_devices = self.recorder.list_windows_video_devices()
            if video_devices:
                for d in video_devices:
                    logger.info(f"  {d}")

            logger.info("\n--- 屏幕捕获说明 ---")
            logger.info("  gdigrab: 默认方式，兼容性好，但硬件加速视频可能黑屏")
            logger.info("  如果视频区域黑屏，请在浏览器中关闭硬件加速")
            logger.info("  Chrome设置: 设置 -> 系统 -> 关闭「使用图形加速」")

        elif sys.platform == "darwin":
            logger.info("macOS 使用 avfoundation 捕获屏幕和音频")
            logger.info("屏幕: Capture screen 0 (主显示器)")
            logger.info("音频: :0 (系统默认音频输入)")
            logger.info("如需捕获系统内部音频，请安装 LoopBack 或 BlackHole")
        else:
            logger.info("Linux 使用 x11grab 捕获屏幕")
            logger.info(f"显示器: {os.environ.get('DISPLAY', ':0')}")
            logger.info("音频: pulse (系统默认音频)")

    def cmd_settings(self, args):
        logger.info(f"当前设置:")
        logger.info(f"  录制目录: {self.settings.recordings_dir}")
        logger.info(f"  画质: {self.settings.quality}")
        logger.info(f"  帧率: {self.settings.frame_rate}")
        logger.info(f"  浏览器可见: {self.settings.show_browser}")
        logger.info(f"  Cookie 文件: {self.settings.get_cookie_path()}")

        if args.set:
            parts = args.set.split("=", 1)
            if len(parts) != 2:
                logger.error("格式错误，请使用 key=value 格式")
                return
            key, value = parts
            if key in ("recordings_dir", "quality", "frame_rate", "headless", "show_browser"):
                if key == "recordings_dir":
                    self.settings.recordings_dir = value
                elif key in ("headless", "show_browser"):
                    self.settings._data[key] = value.lower() == "true"
                elif key == "frame_rate":
                    self.settings._data[key] = int(value)
                else:
                    self.settings._data[key] = value
                self.settings.save()
                logger.info(f"已设置 {key} = {value}")
            else:
                logger.error(f"未知设置项: {key}")


def main():
    app = CourseRecorderApp()
    app.start()

    parser = argparse.ArgumentParser(
        description="小鹅通课程录制工具（支持 macOS / Windows / Linux）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s login                          # 登录小鹅通（首次使用）
  %(prog)s add "课程名称" --url https://...  # 添加课程
  %(prog)s add "课程名称" --url https://... --time 19:30  # 添加定时录制
  %(prog)s list                           # 查看已添加的课程
  %(prog)s record --name "课程名称"         # 立即录制
  %(prog)s record --url https://...       # 通过 URL 立即录制
  %(prog)s records                        # 查看录制记录
  %(prog)s schedule                       # 启动定时录制
  %(prog)s devices                        # 检测系统录制设备（Windows 排查用）

Windows 用户注意事项:
  1. 需安装 ffmpeg: https://ffmpeg.org/download.html (添加到 PATH)
  2. 运行 devices 命令检测音频设备
  3. 如需录制系统声音，安装 VB-Cable: https://vb-audio.com/Cable/
  4. Playwright 会自动下载 Chromium 浏览器
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    login_parser = subparsers.add_parser("login", help="登录小鹅通（保存 Cookie）")

    add_parser = subparsers.add_parser("add", help="添加课程")
    add_parser.add_argument("name", help="课程名称")
    add_parser.add_argument("--url", "-u", required=True, help="课程页面 URL")
    add_parser.add_argument("--time", "-t", help="定时录制时间 (格式: HH:MM)")
    add_parser.add_argument("--audio-only", "-a", action="store_true", help="仅录制音频")

    list_parser = subparsers.add_parser("list", help="查看已添加的课程和录制统计")
    subparsers.add_parser("ls", help="查看已添加的课程（list 的别名）")

    remove_parser = subparsers.add_parser("remove", help="移除课程")
    remove_parser.add_argument("name", help="课程名称")

    record_parser = subparsers.add_parser("record", help="立即录制课程")
    record_parser.add_argument("--name", "-n", help="已保存的课程名称")
    record_parser.add_argument("--url", "-u", help="课程页面 URL（临时录制）")
    record_parser.add_argument("--audio-only", "-a", action="store_true", help="仅录制音频")
    record_parser.add_argument("--duration", "-d", type=int, help="录制时长（秒），不指定则手动停止")

    records_parser = subparsers.add_parser("records", help="查看录制记录")
    records_parser.add_argument("--name", "-n", help="按课程名称筛选")

    delete_parser = subparsers.add_parser("delete-record", help="删除录制记录")
    delete_parser.add_argument("id", help="记录 ID")

    subparsers.add_parser("schedule", help="启动定时录制调度器")

    settings_parser = subparsers.add_parser("settings", help="查看/修改设置")
    settings_parser.add_argument("--set", "-s", help="修改设置 (格式: key=value)")

    subparsers.add_parser("devices", help="检测系统可用的录制设备（摄像头、麦克风等）")

    args = parser.parse_args()

    if args.command == "login":
        app.cmd_login(args)
    elif args.command == "add":
        app.cmd_add(args)
    elif args.command in ("list", "ls"):
        app.cmd_list(args)
    elif args.command == "remove":
        app.cmd_remove(args)
    elif args.command == "record":
        app.cmd_record(args)
    elif args.command == "records":
        app.cmd_records(args)
    elif args.command == "delete-record":
        app.cmd_delete_record(args)
    elif args.command == "schedule":
        app.cmd_schedule(args)
    elif args.command == "settings":
        app.cmd_settings(args)
    elif args.command == "devices":
        app.cmd_devices(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
