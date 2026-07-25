"""集中读取环境变量，避免把联盟、浏览器和监控参数散落在业务代码中。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    enrichment_enabled: bool = False
    request_timeout: float = 20.0
    screenshot_enabled: bool = False
    screenshot_width: int = 1920
    screenshot_height: int = 2160
    screenshot_timeout_ms: int = 45_000
    screenshot_wait_ms: int = 1_500
    screenshot_dir: str = "assets/screenshots"
    browser_executable_path: str = ""
    pricing_enabled: bool = True
    pricing_timeout: float = 20.0
    history_file: str = "data/product_history.json"
    monitor_max_products: int = 10
    ranking_days: int = 30
    ranking_limit: int = 5
    ranking_enabled: bool = False
    affiliate_id: str = ""
    affiliate_link: str = ""
    affiliate_link_template: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            enrichment_enabled=_bool("ENRICHMENT_ENABLED", False),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
            screenshot_enabled=_bool("SCREENSHOT_ENABLED", False),
            screenshot_width=int(os.getenv("SCREENSHOT_WIDTH", "1920")),
            screenshot_height=int(os.getenv("SCREENSHOT_HEIGHT", "2160")),
            screenshot_timeout_ms=int(os.getenv("SCREENSHOT_TIMEOUT_MS", "45000")),
            screenshot_wait_ms=int(os.getenv("SCREENSHOT_WAIT_MS", "1500")),
            screenshot_dir=os.getenv("SCREENSHOT_DIR", "assets/screenshots"),
            browser_executable_path=os.getenv("BROWSER_EXECUTABLE_PATH", "").strip(),
            pricing_enabled=_bool("PRICING_ENABLED", True),
            pricing_timeout=float(os.getenv("PRICING_TIMEOUT_SECONDS", "20")),
            history_file=os.getenv("HISTORY_FILE", "data/product_history.json"),
            monitor_max_products=int(os.getenv("MONITOR_MAX_PRODUCTS", "10")),
            ranking_days=int(os.getenv("RANKING_DAYS", "30")),
            ranking_limit=int(os.getenv("RANKING_LIMIT", "5")),
            ranking_enabled=_bool("RANKING_ENABLED", False),
            affiliate_id=os.getenv("AFFILIATE_ID", "").strip(),
            affiliate_link=os.getenv("AFFILIATE_LINK", "").strip(),
            affiliate_link_template=os.getenv("AFFILIATE_LINK_TEMPLATE", "").strip(),
        )
