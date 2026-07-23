"""科技工具推荐站的每日自动化入口。"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from build import build_site
from fetcher import fetch_new_products, mark_processed
from generator import generate_article


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> int:
    load_dotenv()
    configure_logging()
    logger = logging.getLogger(__name__)
    processed_file = Path(os.getenv("PROCESSED_IDS_FILE", "processed_ids.txt"))

    try:
        products = fetch_new_products(processed_file=processed_file)
    except Exception:
        logger.exception("抓取 Product Hunt Feed 失败")
        return 1

    max_items = int(os.getenv("MAX_PRODUCTS_PER_RUN", "0"))
    if max_items > 0:
        products = products[:max_items]
    logger.info("发现 %d 个待生成产品", len(products))

    content_mode = (os.getenv("CONTENT_MODE") or "template").strip().lower()
    if products and content_mode == "openai" and not os.getenv("OPENAI_API_KEY"):
        logger.error("OpenAI 模式存在待生成产品，但未配置 OPENAI_API_KEY")
        return 1

    generated = 0
    failed = 0
    for product in products:
        article_path = generate_article(product)
        if article_path is None:
            failed += 1
            continue
        mark_processed(product["link"], processed_file)
        generated += 1

    try:
        total = build_site()
    except Exception:
        logger.exception("静态网站构建失败")
        return 1

    logger.info(
        "运行摘要：Feed 新产品 %d，成功生成 %d，生成失败 %d，站内文章 %d",
        len(products), generated, failed, total,
    )
    return 1 if products and generated == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
