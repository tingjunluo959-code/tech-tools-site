"""Product Hunt Feed 抓取与去重模块。"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import requests

LOGGER = logging.getLogger(__name__)

# 按需求保留旧 RSS 地址；Product Hunt 当前返回 404 时自动回退到 Atom 地址。
DEFAULT_FEED_URL = "https://www.producthunt.com/feed.rss"
FALLBACK_FEED_URL = "https://www.producthunt.com/feed"
DEFAULT_PROCESSED_FILE = Path("processed_ids.txt")
USER_AGENT = "TechToolsRecommendationBot/1.0 (+static-site-generator)"


def product_id(link: str) -> str:
    """用稳定的 SHA-256 哈希标识产品链接。"""
    return hashlib.sha256(link.strip().encode("utf-8")).hexdigest()


def load_processed_ids(path: Path = DEFAULT_PROCESSED_FILE) -> set[str]:
    """读取已处理 ID；空行和注释会被忽略。"""
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def save_processed_ids(ids: Iterable[str], path: Path = DEFAULT_PROCESSED_FILE) -> None:
    """排序后一次性写入，便于 Git 审查和重复运行。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    values = sorted(set(ids))
    path.write_text("".join(f"{value}\n" for value in values), encoding="utf-8")


def mark_processed(link: str, path: Path = DEFAULT_PROCESSED_FILE) -> None:
    """仅在文章成功落盘后调用，避免生成失败造成数据丢失。"""
    ids = load_processed_ids(path)
    ids.add(product_id(link))
    save_processed_ids(ids, path)


def _plain_text(raw_html: str) -> str:
    """从 Feed 的简单 HTML 摘要中提取可用于提示词的纯文本。"""
    # Product Hunt Atom 的第一段是产品简介，后续段落只是 Discussion/Link 导航。
    first_paragraph = re.search(r"<p\b[^>]*>(.*?)</p>", raw_html, flags=re.I | re.S)
    if first_paragraph:
        raw_html = first_paragraph.group(1)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def _first_text(node: ET.Element, paths: list[str], namespaces: dict[str, str]) -> str:
    for path in paths:
        found = node.find(path, namespaces)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    """解析 Product Hunt 的 Atom 或传统 RSS 2.0 XML。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Feed XML 解析失败: {exc}") from exc

    atom = {"atom": "http://www.w3.org/2005/Atom"}
    is_atom = root.tag.endswith("feed")
    entries = root.findall("atom:entry", atom) if is_atom else root.findall("./channel/item")
    products: list[dict[str, str]] = []

    for entry in entries:
        if is_atom:
            title = _first_text(entry, ["atom:title"], atom)
            description = _first_text(entry, ["atom:summary", "atom:content"], atom)
            category_node = entry.find("atom:category", atom)
            category = ""
            if category_node is not None:
                category = (category_node.get("term") or category_node.text or "").strip()
            link = ""
            for link_node in entry.findall("atom:link", atom):
                if link_node.get("rel", "alternate") == "alternate":
                    link = (link_node.get("href") or "").strip()
                    if link:
                        break
        else:
            title = _first_text(entry, ["title"], {})
            description = _first_text(entry, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"], {})
            category = _first_text(entry, ["category"], {})
            link = _first_text(entry, ["link"], {})

        # 标题或链接缺失时无法可靠生成、去重，因此跳过异常条目。
        if not title or not link:
            LOGGER.warning("跳过缺少标题或链接的 Feed 条目")
            continue
        products.append(
            {
                "title": html.unescape(title),
                "link": link,
                "description": _plain_text(description),
                "category": html.unescape(category) if category else "未分类",
            }
        )
    return products


def _download_feed(url: str, timeout: float) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def fetch_new_products(
    processed_file: Path = DEFAULT_PROCESSED_FILE,
    feed_url: str | None = None,
) -> list[dict[str, str]]:
    """下载 Feed，并返回尚未成功生成过文章的产品。"""
    url = feed_url or os.getenv("PRODUCT_HUNT_FEED_URL", DEFAULT_FEED_URL)
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    try:
        xml_text = _download_feed(url, timeout)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if url == DEFAULT_FEED_URL and status == 404:
            LOGGER.warning("默认 Feed 地址返回 404，自动回退到 %s", FALLBACK_FEED_URL)
            xml_text = _download_feed(FALLBACK_FEED_URL, timeout)
        else:
            raise

    processed = load_processed_ids(processed_file)
    return [product for product in parse_feed(xml_text) if product_id(product["link"]) not in processed]
