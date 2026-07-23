"""用本地模板或可选 OpenAI 模式生成中文推荐文章。"""

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
    """生成稳定、适合 URL 的文件名；哈希可避免同名产品冲突。"""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "product"
    suffix = hashlib.sha256(link.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"


def build_prompt(product: dict[str, str]) -> str:
    """提示模型只依据 Feed 信息写作，避免虚构亲自使用的经历。"""
    return f"""请根据以下 Product Hunt Feed 信息，写一篇 400-600 个中文字的中文科技工具推荐文。

产品名称：{product['title']}
产品描述：{product['description'] or 'Feed 未提供描述'}
产品分类：{product['category']}

写作要求：
1. 使用自然、亲切、易读的推荐语气，但不得声称你亲自使用、测试或购买过该产品，也不得虚构功能、价格、评价或效果。
2. 简要说明已知功能、可能解决的问题和适合人群；信息不足时明确使用“从官方简介来看”等限定语。
3. 使用 Markdown 正文，可包含二级标题和列表；不要输出文章主标题、front matter 或代码围栏。
4. 在文中自然且只插入一次 Markdown 链接：[了解更多]({AFFILIATE_PLACEHOLDER})。
5. 结尾提醒读者在购买或订阅前核对官网的最新功能、价格与条款。
"""


def _chinese_character_count(text: str) -> int:
    """统计中文字符，用于验证模型是否满足 400–600 字要求。"""
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))


def _escape_markdown_text(value: str) -> str:
    """转义 Feed 文本中的 Markdown 控制字符，避免破坏正文结构。"""
    return re.sub(r"([\\`*_[\]<>])", r"\\\1", value.strip())


def generate_template_article(product: dict[str, str]) -> str:
    """不调用外部 AI，依据有限 Feed 信息生成诚实、可发布的中文稿。"""
    title = _escape_markdown_text(product["title"])
    description = _escape_markdown_text(product["description"] or "官方 Feed 暂未提供详细简介")
    category = _escape_markdown_text(product["category"] or "未分类")
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


def generate_article(
    product: dict[str, str],
    client: OpenAI | None = None,
    content_dir: Path = CONTENT_DIR,
) -> Path | None:
    """生成一篇文章；默认本地模板，OpenAI 模式失败时重试 2 次。"""
    mode = (os.getenv("CONTENT_MODE") or "template").strip().lower()
    # 测试或调用方显式传入客户端时，视为要求走 OpenAI 兼容流程。
    if client is not None:
        mode = "openai"

    if mode == "template":
        try:
            article = generate_template_article(product)
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.error("本地模板生成 %s 失败：%s", product.get("title", "未知产品"), exc)
            return None
    elif mode == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if client is None:
            if not api_key:
                LOGGER.error("OpenAI 模式未配置 OPENAI_API_KEY")
                return None
            client = OpenAI(api_key=api_key)

        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        attempts = 3
        article = ""
        for attempt in range(1, attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是严谨的中文科技编辑。忠于输入资料，不编造亲身体验或未经提供的事实。",
                        },
                        {"role": "user", "content": build_prompt(product)},
                    ],
                    temperature=0.7,
                )
                article = (response.choices[0].message.content or "").strip()
                if not article:
                    raise ValueError("OpenAI 返回了空内容")
                character_count = _chinese_character_count(article)
                if not 400 <= character_count <= 600:
                    raise ValueError(f"正文中文字数为 {character_count}，不在 400–600 范围内")
                if AFFILIATE_PLACEHOLDER not in article:
                    article += f"\n\n[了解更多]({AFFILIATE_PLACEHOLDER})"
                break
            except Exception as exc:  # SDK 的网络/限流/响应异常类型可能不同
                LOGGER.warning("生成 %s 失败（第 %d/%d 次）：%s", product["title"], attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(float(os.getenv("OPENAI_RETRY_DELAY_SECONDS", "2")) * attempt)
        else:
            LOGGER.error("生成 %s 连续失败，已跳过", product["title"])
            return None
    else:
        LOGGER.error("不支持的 CONTENT_MODE=%s，仅支持 template 或 openai", mode)
        return None

    now = datetime.now(timezone.utc)
    # 日期前缀可避免去重文件被误删后，同一产品跨日重生成时覆盖旧页面。
    slug = f"{now:%Y-%m-%d}-{_slugify(product['title'], product['link'])}"
    post = frontmatter.Post(article)
    post.metadata.update(
        {
            "title": f"{product['title']}：值得关注的科技工具",
            "date": now.isoformat(timespec="seconds"),
            "category": product["category"],
            "original_link": product["link"],
            "slug": slug,
        }
    )
    content_dir.mkdir(parents=True, exist_ok=True)
    output_path = content_dir / f"{slug}.md"
    output_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    LOGGER.info("文章已保存：%s", output_path)
    return output_path
