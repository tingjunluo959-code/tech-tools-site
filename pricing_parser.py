"""从公开 Pricing 页面提取可核验的套餐快照。

网页结构高度不统一，因此这里采用保守的启发式解析：宁可返回空数据，也不
把普通营销文字误当成价格。输出必须在文章中标注“请以官网为准”。"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import Settings

LOGGER = logging.getLogger(__name__)
USER_AGENT = "TechToolsRecommendationBot/1.0 (+static-site-generator)"
PLAN_NAMES = ("free", "pro", "team", "business", "enterprise", "starter", "basic", "growth")
PROMOTION_RE = re.compile(r"(?:black friday|cyber monday|up to\s+\d+%\s*off|\d+%\s*off|free trial|limited[- ]time|优惠|折扣|免费试用)", re.I)
PRICE_RE = re.compile(r"(?:\$|€|£|¥)\s?\d+(?:[.,]\d+)?(?:\s*/\s*(?:mo|month|monthly|yr|year|年|月))?|(?:free|免费)", re.I)


@dataclass(frozen=True)
class PricingPlan:
    plan: str
    price: str
    features: list[str]
    recommended: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _pricing_url(official_url: str) -> str:
    parsed = urlparse(official_url)
    base = f"{parsed.scheme}://{parsed.netloc}/"
    return urljoin(base, "pricing")


def parse_pricing_html(html_text: str) -> tuple[list[dict[str, object]], list[str]]:
    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    promotions = sorted(set(match.group(0).strip() for match in PROMOTION_RE.finditer(soup.get_text(" ", strip=True))))
    plans: list[PricingPlan] = []
    seen: set[str] = set()
    for node in soup.find_all(["article", "section", "div", "li"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if len(text) < 12 or len(text) > 1200:
            continue
        lower = text.lower()
        plan_name = next((name for name in PLAN_NAMES if re.search(rf"\b{re.escape(name)}\b", lower)), None)
        price_match = PRICE_RE.search(text)
        if not plan_name or not price_match:
            continue
        key = f"{plan_name}|{price_match.group(0).lower()}"
        if key in seen:
            continue
        seen.add(key)
        feature_texts = []
        for item in node.find_all("li")[:6]:
            value = " ".join(item.get_text(" ", strip=True).split())
            if value and value.lower() != text.lower():
                feature_texts.append(value[:180])
        plans.append(PricingPlan(plan_name.title(), html.unescape(price_match.group(0)), feature_texts, False))
    # 去重后最多展示四个套餐；推荐规则只基于已解析数据，不声称性价比事实。
    unique: dict[str, PricingPlan] = {}
    for plan in plans:
        unique.setdefault(plan.plan.lower(), plan)
    selected = list(unique.values())[:4]
    paid = [p for p in selected if p.price.lower() not in {"free", "免费"} and p.plan.lower() != "enterprise"]
    recommended_name = paid[0].plan if paid else (selected[0].plan if selected else "")
    result = [PricingPlan(p.plan, p.price, p.features, p.plan == recommended_name).as_dict() for p in selected]
    return result, promotions


def fetch_pricing(official_url: str, settings: Settings | None = None) -> dict[str, object]:
    settings = settings or Settings.from_env()
    if not settings.pricing_enabled:
        return {"url": "", "plans": [], "promotions": [], "error": "disabled"}
    url = _pricing_url(official_url)
    try:
        response = requests.get(url, timeout=settings.pricing_timeout, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        plans, promotions = parse_pricing_html(response.text)
        return {"url": response.url, "plans": plans, "promotions": promotions, "error": ""}
    except requests.RequestException as exc:
        LOGGER.info("Pricing 页面不可用 %s：%s", url, exc)
        return {"url": url, "plans": [], "promotions": [], "error": str(exc)[:200]}
