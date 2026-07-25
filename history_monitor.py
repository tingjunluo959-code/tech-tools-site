"""保存价格/促销状态，并把新发现的促销转成文章 Alert 元数据。"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

LOGGER = logging.getLogger(__name__)


def _load(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"products": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"products": {}}
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning("历史状态文件无法读取，将以空状态继续：%s", exc)
        return {"products": {}}


def _signature(state: dict[str, object]) -> str:
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def update_history(product_id: str, official_url: str, pricing: dict[str, object], link_status: dict[str, object], path: Path) -> list[str]:
    """返回本次新出现的促销标识；只有状态变化才写文件，避免每日无意义提交。"""
    data = _load(path)
    products = data.setdefault("products", {})
    old = products.get(product_id, {}) if isinstance(products, dict) else {}
    promotions = [str(item) for item in pricing.get("promotions", [])]
    stable_link_status = {key: link_status.get(key) for key in ("url", "status_code", "ok", "error")}
    state = {"official_url": official_url, "plans": pricing.get("plans", []), "promotions": promotions, "link_status": stable_link_status}
    previous_promotions = set(old.get("promotions", [])) if isinstance(old, dict) else set()
    new_promotions = sorted(set(promotions) - previous_promotions)
    if not isinstance(products, dict):
        data["products"] = products = {}
    if _signature(old if isinstance(old, dict) else {}) != _signature(state):
        products[product_id] = {**state, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    return new_promotions


def known_products(path: Path) -> list[tuple[str, str]]:
    data = _load(path)
    products = data.get("products", {})
    if not isinstance(products, dict):
        return []
    result = []
    for product_id, state in products.items():
        if isinstance(state, dict) and state.get("official_url"):
            result.append((str(product_id), str(state["official_url"])))
    return result


def apply_promotion_alert(content_dir: Path, product_id: str, promotions: list[str]) -> int:
    """为匹配的旧文章写入结构化 alert；模板负责显示在正文顶部。"""
    if not promotions or not content_dir.exists():
        return 0
    changed = 0
    for path in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(path)
            if str(post.get("product_id", "")) != product_id:
                continue
            current = [str(item) for item in post.get("promotion_alerts", [])]
            merged = sorted(set(current + promotions))
            if merged != current:
                post["promotion_alerts"] = merged
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
                changed += 1
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("无法更新促销提醒 %s：%s", path, exc)
    return changed


def apply_product_state(content_dir: Path, product_id: str, pricing: dict[str, object], link_status: dict[str, object]) -> int:
    """把当前价格、促销和链接状态同步到已有文章；只在值变化时写盘。"""
    if not content_dir.exists():
        return 0
    changed = 0
    stable_status = {key: link_status.get(key) for key in ("url", "status_code", "ok", "error")}
    for path in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(path)
            if str(post.get("product_id", "")) != product_id:
                continue
            updates = {
                "pricing": list(pricing.get("plans", [])),
                "pricing_url": str(pricing.get("url", "")),
                "promotion_alerts": [str(item) for item in pricing.get("promotions", [])],
                "link_status": stable_status,
            }
            if any(post.get(key) != value for key, value in updates.items()):
                post.metadata.update(updates)
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
                changed += 1
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("无法同步产品状态 %s：%s", path, exc)
    return changed
