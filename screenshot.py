"""使用 Playwright 截取官网前两屏；浏览器依赖按需懒加载。"""

from __future__ import annotations

import logging
from pathlib import Path

from config import Settings

LOGGER = logging.getLogger(__name__)


def capture_screenshot(url: str, product_id: str, settings: Settings | None = None) -> str | None:
    settings = settings or Settings.from_env()
    if not settings.screenshot_enabled:
        return None
    if not url.startswith(("http://", "https://")):
        return None
    target_dir = Path(settings.screenshot_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{product_id}.png"
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            launch_options: dict[str, object] = {"headless": True}
            if settings.browser_executable_path:
                launch_options["executable_path"] = settings.browser_executable_path
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page(viewport={"width": settings.screenshot_width, "height": 1080}, device_scale_factor=1)
            try:
                page.goto(url, wait_until="networkidle", timeout=settings.screenshot_timeout_ms)
            except PlaywrightTimeoutError:
                LOGGER.info("页面未在 networkidle 前稳定，改用当前已加载内容截图：%s", url)
            page.wait_for_timeout(settings.screenshot_wait_ms)
            page_height = int(page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"))
            capture_height = min(settings.screenshot_height, max(1080, page_height))
            page.screenshot(
                path=str(target),
                clip={"x": 0, "y": 0, "width": settings.screenshot_width, "height": capture_height},
            )
            browser.close()
        return str(target).replace("\\", "/")
    except Exception as exc:  # 浏览器安装、证书、JS 页面等问题不能阻断发文
        LOGGER.warning("截图失败 %s：%s", url, exc)
        return None
