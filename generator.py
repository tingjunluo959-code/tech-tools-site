"""文章生成模块：默认使用本地双语模板，也支持可选 OpenAI。"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
from openai import OpenAI

LOGGER = logging.getLogger(__name__)
CONTENT_DIR = Path("content/posts")
AFFILIATE_PLACEHOLDER = "{{affiliate_link}}"


def _slugify(title: str, link: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "product"
    suffix = hashlib.sha256(link.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"


def build_prompt(product: dict[str, str], language: str = "zh") -> str:
    """构造严格基于 Feed 信息的提示词。"""
    if language == "en":
        return f"""Write a 400-600 word English recommendation article based only on this Product Hunt feed entry.
Product: {product['title']}
Description: {product['description'] or 'No description supplied by the feed'}
Category: {product['category']}

Use a friendly, practical tone. Do not claim personal use, testing, pricing, reviews, or results that are not in the source. Explain the known purpose, likely audience, and sensible checks before subscribing. Output Markdown body only (no title, front matter, or code fence). Include exactly one natural link [Learn more]({AFFILIATE_PLACEHOLDER}) and remind readers to verify current details on the official site."""
    return f"""请根据以下 Product Hunt Feed 信息，写一篇 400-600 个中文字的中文科技工具推荐文。
产品名称：{product['title']}
产品描述：{product['description'] or 'Feed 未提供描述'}
产品分类：{product['category']}

语气亲切但不得声称亲自使用、测试或购买过产品，也不得虚构功能、价格、评价或效果。只输出 Markdown 正文，不要输出标题、front matter 或代码围栏。自然且只插入一次 [了解更多]({AFFILIATE_PLACEHOLDER})，并提醒读者在官网核对最新信息。"""


def _chinese_character_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def _escape_markdown_text(value: str) -> str:
    return re.sub(r"([\\`*_[\]<>])", r"\\\1", value.strip())


def generate_template_article(product: dict[str, str]) -> str:
    """生成无需外部账号的中文模板文章。"""
    title = _escape_markdown_text(product["title"])
    description = _escape_markdown_text(product.get("description") or "官方 Feed 暂未提供详细简介")
    category = _escape_markdown_text(product.get("category") or "未分类")
    article = f"""## 产品速览

{title} 是近期出现在 Product Hunt 上的一款科技产品，目前 Feed 将它归在“{category}”类别。官方 Feed 给出的原始简介是：

> {description}

从这段公开信息来看，它更适合被当作一个值得进一步了解的新工具。由于 Feed 提供的资料有限，本文不会补写未经官方确认的功能、价格、用户评价或使用效果。

## 为什么值得留意

新工具的价值通常不只取决于功能数量，更取决于它能否减少重复步骤、降低学习成本，或者让原本分散的工作更容易管理。{title} 的简介至少提供了一个观察入口：读者可以先判断它所针对的问题是否与自己的实际需求重合，再决定是否投入时间试用。建议先查看演示、帮助文档和更新记录。

## 可能适合的人

- 正在寻找新效率工具，并愿意小范围试用后再决定的人；
- 已经有明确任务，希望比较不同解决方案，而不是盲目追逐热门产品的人；
- 负责团队选型，需要先收集候选工具，再评估权限、协作和数据安全的人。

如果你现在的工作流程已经稳定，也没有明确痛点，可以暂时收藏并观察后续更新。工具是否合适，最终仍取决于使用场景、预算、学习成本以及能否顺利导出数据。

## 使用前建议

建议先通过[了解更多]({AFFILIATE_PLACEHOLDER})查看最新页面，重点核对免费额度、订阅价格、取消方式、数据保存位置、隐私政策和客服渠道。若产品需要连接邮箱、云盘、代码仓库或团队资料，应先用非敏感测试数据体验，并确认授权可以随时撤销。涉及公司数据时，还应由负责人检查合规和权限边界。

总体而言，{title} 值得作为候选工具继续观察，但现有 Feed 信息不足以支持强结论。购买或订阅前，请以产品官网的最新功能、价格和服务条款为准，并根据真实试用结果作决定。"""
    count = _chinese_character_count(article)
    if not 400 <= count <= 600:
        raise ValueError(f"本地模板正文中文字数为 {count}，不在 400–600 范围内")
    return article


def generate_template_article_en(product: dict[str, str]) -> str:
    """生成英文镜像文章；只陈述 Feed 已公开的信息。"""
    title = product.get("title", "New product").strip()
    description = product.get("description") or "The Product Hunt feed does not include a detailed description."
    category = product.get("category") or "Uncategorized"
    return f"""## Quick overview

**{title}** is a recent Product Hunt launch listed in the **{category}** category. The public feed describes it this way:

> {description}

That short description is a useful starting point, but it is not a substitute for the product's own documentation. This article intentionally avoids inventing features, prices, reviews, performance claims, or first-hand experience.

## Why it may be worth a closer look

New tools are most useful when they remove repetitive work, make a complicated workflow easier to understand, or help a small team keep information in one place. Based on the feed entry alone, {title} is best treated as a candidate for further research rather than a guaranteed solution. Start by comparing the problem it claims to address with the way you work today. A short demo, a changelog, and the help center often reveal more than a launch headline.

## Who may find it useful

- People exploring productivity or development tools and willing to test them in a limited, low-risk setting;
- Buyers with a clearly defined task who want to compare several approaches before committing;
- Team leads who need to review permissions, collaboration features, export options, and data handling.

If your current workflow is stable and no clear pain point exists, bookmarking the launch and watching future updates may be the most sensible next step. Fit depends on context, budget, learning time, and whether your data can be exported when needed.

## Checks before subscribing

Use [Learn more]({AFFILIATE_PLACEHOLDER}) to open the latest product page. Confirm the current free allowance, subscription price, cancellation process, storage location, privacy policy, support channel, and any limits on integrations. If the tool requests access to email, cloud storage, source code, or team documents, begin with non-sensitive test data and verify that permissions can be revoked. For business use, ask the relevant owner to review security and compliance boundaries.

Overall, {title} is an interesting candidate to monitor, but the available feed information is not enough for a strong recommendation. Verify current details on the official site and decide from a real, appropriately scoped trial."""


def _openai_article(product: dict[str, str], client: OpenAI, language: str) -> str | None:
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a careful technology editor. Never invent facts or personal experience."},
                    {"role": "user", "content": build_prompt(product, language)},
                ],
                temperature=0.7,
            )
            article = (response.choices[0].message.content or "").strip()
            if not article:
                raise ValueError("OpenAI returned empty content")
            if language == "zh":
                count = _chinese_character_count(article)
                if not 400 <= count <= 600:
                    raise ValueError(f"Chinese character count {count} is outside 400-600")
            elif not 250 <= len(article.split()) <= 800:
                raise ValueError("English article length is outside 250-800 words")
            if AFFILIATE_PLACEHOLDER not in article:
                article += f"\n\n[{'Learn more' if language == 'en' else '了解更多'}]({AFFILIATE_PLACEHOLDER})"
            return article
        except Exception as exc:
            LOGGER.warning("生成 %s/%s 失败（第 %d/3 次）：%s", product.get("title"), language, attempt, exc)
            if attempt < 3:
                time.sleep(float(os.getenv("OPENAI_RETRY_DELAY_SECONDS", "2")) * attempt)
    LOGGER.error("生成 %s/%s 连续失败，已跳过", product.get("title"), language)
    return None


def _generate_one(product: dict[str, str], language: str, client: OpenAI | None, content_dir: Path, now: datetime) -> Path | None:
    mode = (os.getenv("CONTENT_MODE") or "template").strip().lower()
    if client is not None:
        mode = "openai"
    try:
        if mode == "template":
            article = generate_template_article_en(product) if language == "en" else generate_template_article(product)
        elif mode == "openai":
            if client is None:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    LOGGER.error("OpenAI 模式未配置 OPENAI_API_KEY")
                    return None
                client = OpenAI(api_key=api_key)
            article = _openai_article(product, client, language)
            if article is None:
                return None
        else:
            LOGGER.error("不支持的 CONTENT_MODE=%s", mode)
            return None
    except (KeyError, TypeError, ValueError) as exc:
        LOGGER.error("%s 模板生成 %s 失败：%s", language, product.get("title", "未知产品"), exc)
        return None

    base_slug = f"{now:%Y-%m-%d}-{_slugify(product['title'], product['link'])}"
    file_slug = f"{base_slug}-{language}"
    post = frontmatter.Post(article)
    post.metadata.update(
        {
            "title": (f"{product['title']}：值得关注的科技工具" if language == "zh" else f"{product['title']}: A Tool Worth Watching"),
            "date": now.isoformat(timespec="seconds"),
            "category": product.get("category") or "未分类",
            "original_link": product["link"],
            "slug": base_slug,
            "lang": language,
            "translation_slug": base_slug,
        }
    )
    content_dir.mkdir(parents=True, exist_ok=True)
    output_path = content_dir / f"{file_slug}.md"
    output_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    LOGGER.info("%s 文章已保存：%s", language, output_path)
    return output_path


def generate_article(product: dict[str, str], client: OpenAI | None = None, content_dir: Path = CONTENT_DIR, language: str | None = None) -> Path | None:
    """生成单语文章；未指定 language 时生成中英文并要求两者都成功。

    传入 client 的旧调用保持只生成中文，兼容已有 OpenAI 重试测试。
    """
    now = datetime.now(timezone.utc)
    if language in {"zh", "en"}:
        return _generate_one(product, language, client, content_dir, now)
    if client is not None:
        return _generate_one(product, "zh", client, content_dir, now)
    zh = _generate_one(product, "zh", None, content_dir, now)
    en = _generate_one(product, "en", None, content_dir, now)
    if zh is None or en is None:
        LOGGER.error("产品 %s 未能完整生成双语文章", product.get("title", "未知产品"))
        return None
    return zh


def migrate_legacy_posts(content_dir: Path = CONTENT_DIR) -> int:
    """给旧中文文章补元数据，并创建缺失的英文镜像。"""
    if not content_dir.exists():
        return 0
    created = 0
    for path in content_dir.glob("*.md"):
        try:
            post = frontmatter.load(path)
            if post.get("lang") == "en":
                continue
            changed = False
            slug = str(post.get("slug") or path.stem)
            if post.get("lang") != "zh":
                post["lang"] = "zh"; changed = True
            if not post.get("translation_slug"):
                post["translation_slug"] = slug; changed = True
            if changed:
                path.write_text(frontmatter.dumps(post), encoding="utf-8")
            en_path = content_dir / f"{slug}-en.md"
            if en_path.exists():
                continue
            title = str(post.get("title") or slug)
            title = re.sub(r"\s*[：:]值得关注的科技工具\s*$", "", title).strip() or slug
            category = str(post.get("category") or "Uncategorized")
            link = str(post.get("original_link") or "")
            body = f"""## Quick overview\n\n**{title}** is a product discovered through Product Hunt, listed in the **{category}** category. The existing Chinese article is retained as the source for this mirror; no unverified features or first-hand claims are added.\n\n## What to check\n\nRead the official page for the latest product description, documentation, pricing, privacy policy, integrations, and support terms. The available source information is limited, so treat this page as a research note rather than a guarantee.\n\nUse [Learn more]({AFFILIATE_PLACEHOLDER}) to open the original listing. Before sharing sensitive data, test with a non-sensitive account and confirm that permissions can be revoked.\n\nDecide after comparing the tool with your actual workflow and a small, reversible trial."""
            mirror = frontmatter.Post(body)
            mirror.metadata.update({"title": f"{title}: A Tool Worth Watching", "date": post["date"], "category": category, "original_link": link, "slug": slug, "lang": "en", "translation_slug": slug})
            en_path.write_text(frontmatter.dumps(mirror), encoding="utf-8")
            created += 1
        except (OSError, TypeError, ValueError) as exc:
            LOGGER.warning("旧文章迁移失败 %s：%s", path, exc)
    return created
