import os
import json
import time
import logging
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class CourseBrowser:
    XIAOETONG_DOMAIN = "xiaoetong.com"

    def __init__(self, settings: "Settings"):
        self.settings = settings
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def is_logged_in(self) -> bool:
        cookie_path = self.settings.get_cookie_path()
        return os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 0

    def start(self):
        logger.info("启动浏览器...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.settings.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )

        self._context.set_default_timeout(self.settings.page_load_timeout * 1000)
        self._load_cookies()
        self._page = self._context.new_page()
        logger.info("浏览器启动完成")

    def stop(self):
        logger.info("关闭浏览器...")
        try:
            if self._context:
                self._save_cookies()
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.warning(f"关闭浏览器时出错: {e}")

    def _load_cookies(self):
        cookie_path = self.settings.get_cookie_path()
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                if cookies:
                    self._context.add_cookies(cookies)
                    logger.info(f"已加载 {len(cookies)} 个 Cookie")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"加载 Cookie 失败: {e}")

    def _save_cookies(self):
        if not self._context:
            return
        try:
            cookies = self._context.cookies()
            cookie_path = self.settings.get_cookie_path()
            with open(cookie_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(cookies)} 个 Cookie")
        except Exception as e:
            logger.warning(f"保存 Cookie 失败: {e}")

    def navigate(self, url: str) -> Page:
        logger.info(f"导航到: {url}")
        self._page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)
        return self._page

    def wait_for_login(self, timeout_seconds: int = 300) -> bool:
        logger.info("等待用户登录...")
        self._page.goto(
            f"https://admin.xiaoetong.com",
            wait_until="domcontentloaded",
        )

        start = time.time()
        while time.time() - start < timeout_seconds:
            if self._is_logged_in_to_xet():
                logger.info("检测到登录成功")
                self._save_cookies()
                return True
            time.sleep(2)

        logger.error("登录超时")
        return False

    def _is_logged_in_to_xet(self) -> bool:
        try:
            cookies = self._context.cookies()
            for c in cookies:
                if self.XIAOETONG_DOMAIN in c.get("domain", ""):
                    return True
            return False
        except Exception:
            return False

    def detect_video_element(self, timeout: int = 30) -> bool:
        logger.info("检测视频播放元素...")
        try:
            self._page.wait_for_selector("video", timeout=timeout * 1000)
            logger.info("检测到视频元素")
            return True
        except Exception:
            logger.warning("未检测到视频元素")
            return False

    def detect_audio_element(self, timeout: int = 15) -> bool:
        logger.info("检测音频播放元素...")
        try:
            self._page.wait_for_selector("audio", timeout=timeout * 1000)
            logger.info("检测到音频元素")
            return True
        except Exception:
            logger.warning("未检测到音频元素")
            return False

    def try_play_video(self):
        logger.info("尝试自动播放视频...")
        try:
            self._page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    if (video) {
                        video.muted = false;
                        video.volume = 1.0;
                        video.play().catch(e => console.error('自动播放失败:', e));
                    }
                }
            """)
        except Exception as e:
            logger.warning(f"自动播放尝试失败: {e}")

    def get_video_info(self) -> dict:
        try:
            info = self._page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    if (!video) return null;
                    return {
                        duration: video.duration || 0,
                        currentTime: video.currentTime || 0,
                        paused: video.paused,
                        width: video.videoWidth || 0,
                        height: video.videoHeight || 0,
                        src: video.currentSrc || video.src || '',
                    };
                }
            """)
            return info or {}
        except Exception as e:
            logger.warning(f"获取视频信息失败: {e}")
            return {}

    def get_page_title(self) -> str:
        try:
            return self._page.title()
        except Exception:
            return "未知课程"

    def wait_for_playback_start(self, timeout: int = 60) -> bool:
        logger.info("等待视频开始播放...")
        start = time.time()
        last_time = 0
        stable_count = 0

        while time.time() - start < timeout:
            info = self.get_video_info()
            if info:
                current = info.get("currentTime", 0)
                if current > 0 and not info.get("paused", True):
                    if current > last_time:
                        stable_count += 1
                        if stable_count >= 3:
                            logger.info(f"视频正在播放中 (当前进度: {current:.1f}s)")
                            return True
                    last_time = current
                else:
                    self.try_play_video()
            time.sleep(2)

        logger.warning("等待视频播放超时")
        return False

    def get_playback_position(self) -> float:
        info = self.get_video_info()
        return info.get("currentTime", 0)

    def screenshot(self, path: str):
        try:
            self._page.screenshot(path=path)
        except Exception as e:
            logger.warning(f"截图失败: {e}")
