"""官网链接解析和可用性检查。"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import Settings

LOGGER = logging.getLogger(__name__)
USER_AGENT = "TechToolsRecommendationBot/1.0 (+static-site-generator)"
PRODUCT_HUNT_HOSTS = {"producthunt.com", "www.producthunt.com"}


@dataclass(frozen=True)
class LinkStatus:
    url: str
    status_code: int | None
    ok: bool
    checked_at: str
    error: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        address = ipaddress.ip_address(host)
        return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)
    except ValueError:
        return True


def check_url(url: str, settings: Settings | None = None) -> LinkStatus:
    """先 HEAD、失败后 GET；网络失败不会阻断整条内容流水线。"""
    settings = settings or Settings.from_env()
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not _safe_public_url(url):
        return LinkStatus(url, None, False, checked_at, "invalid or non-public URL")
    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=settings.request_timeout,
            headers={"User-Agent": USER_AGENT},
        )
        # 一些官网不实现 HEAD，用轻量 GET 重试一次。
        if response.status_code in {405, 403}:
            response = requests.get(url, allow_redirects=True, stream=True, timeout=settings.request_timeout, headers={"User-Agent": USER_AGENT})
        ok = 200 <= response.status_code < 400
        return LinkStatus(url, response.status_code, ok, checked_at, "" if ok else f"HTTP {response.status_code}")
    except requests.RequestException as exc:
        LOGGER.warning("官网链接检查失败 %s：%s", url, exc)
        return LinkStatus(url, None, False, checked_at, str(exc)[:200])


def resolve_official_url(product_hunt_url: str, settings: Settings | None = None) -> str:
    """从 Product Hunt 页面寻找外链；解析失败时保留原始 Product Hunt URL。"""
    settings = settings or Settings.from_env()
    if not _safe_public_url(product_hunt_url):
        return product_hunt_url
    try:
        response = requests.get(product_hunt_url, timeout=settings.request_timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        candidates: list[str] = []
        canonical = soup.find("link", rel="canonical")
        # 优先选择带有 Product Hunt 外链常见标记的按钮。
        for anchor in soup.select("a[href]"):
            href = urljoin(response.url, anchor.get("href", "").strip())
            text = " ".join(anchor.get_text(" ", strip=True).lower().split())
            if href and ("visit" in text or "website" in text or "get started" in text):
                candidates.insert(0, href)
            elif href:
                candidates.append(href)
        for candidate in candidates:
            parsed = urlparse(candidate)
            if parsed.hostname and parsed.hostname.lower() not in PRODUCT_HUNT_HOSTS and _safe_public_url(candidate):
                return candidate
        if canonical and canonical.get("href"):
            return urljoin(response.url, canonical["href"])
    except (requests.RequestException, ValueError, OSError, socket.error) as exc:
        LOGGER.info("无法解析 Product Hunt 外链 %s：%s", product_hunt_url, exc)
    # Product Hunt 的 /r/ 出站链接常对 requests 返回 403；无头浏览器通常仍能跟随。
    if settings.screenshot_enabled:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                options: dict[str, object] = {"headless": True}
                if settings.browser_executable_path:
                    options["executable_path"] = settings.browser_executable_path
                browser = playwright.chromium.launch(**options)
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(product_hunt_url, wait_until="domcontentloaded", timeout=settings.screenshot_timeout_ms)
                final_url = page.url
                browser.close()
            host = urlparse(final_url).hostname
            if host and host.lower() not in PRODUCT_HUNT_HOSTS and _safe_public_url(final_url):
                return final_url
        except Exception as exc:
            LOGGER.info("浏览器无法解析 Product Hunt 出站链接 %s：%s", product_hunt_url, exc)
    return product_hunt_url
