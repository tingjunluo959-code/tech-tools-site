"""把链接解析、截图、定价和历史监控组合成可容错的富化流水线。"""

from __future__ import annotations

import logging
from pathlib import Path

from config import Settings
from fetcher import product_id
from history_monitor import apply_product_state, known_products, update_history
from link_checker import check_url, resolve_official_url
from pricing_parser import fetch_pricing
from screenshot import capture_screenshot

LOGGER = logging.getLogger(__name__)


def enrich_product(product: dict[str, object], settings: Settings | None = None) -> dict[str, object]:
    settings = settings or Settings.from_env()
    enriched = dict(product)
    pid = product_id(str(product["link"]))
    source_url = str(product.get("redirect_url") or product["link"])
    official_url = resolve_official_url(source_url, settings)
    # 出站解析失败时，文章仍以 Product Hunt 原始页作为可审计来源。
    if official_url == source_url and product.get("redirect_url"):
        official_url = str(product["link"])
    status = check_url(official_url, settings)
    pricing = fetch_pricing(official_url, settings) if status.ok else {"url": "", "plans": [], "promotions": [], "error": status.error}
    screenshot = capture_screenshot(official_url, pid, settings) if status.ok else None
    enriched.update({"product_id": pid, "official_url": official_url, "link_status": status.as_dict(), "pricing": pricing, "screenshot": screenshot or ""})
    return enriched


def record_product_state(product: dict[str, object], settings: Settings | None = None, content_dir: Path = Path("content/posts")) -> int:
    settings = settings or Settings.from_env()
    update_history(
        str(product["product_id"]),
        str(product["official_url"]),
        dict(product.get("pricing") or {}),
        dict(product.get("link_status") or {}),
        Path(settings.history_file),
    )
    return apply_product_state(content_dir, str(product["product_id"]), dict(product.get("pricing") or {}), dict(product.get("link_status") or {}))


def monitor_existing_products(settings: Settings | None = None, content_dir: Path = Path("content/posts"), skip_ids: set[str] | None = None) -> int:
    settings = settings or Settings.from_env()
    skip_ids = skip_ids or set()
    alerts = 0
    for pid, official_url in known_products(Path(settings.history_file))[: max(0, settings.monitor_max_products)]:
        if pid in skip_ids:
            continue
        try:
            status = check_url(official_url, settings)
            pricing = fetch_pricing(official_url, settings) if status.ok else {"url": "", "plans": [], "promotions": [], "error": status.error}
            update_history(pid, official_url, pricing, status.as_dict(), Path(settings.history_file))
            alerts += apply_product_state(content_dir, pid, pricing, status.as_dict())
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("监控产品 %s 失败，继续处理其他产品：%s", pid, exc)
    return alerts
