"""把 Markdown 内容构建成可部署到 GitHub Pages 的静态网站。"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

LOGGER = logging.getLogger(__name__)
CONTENT_DIR = Path("content/posts")
TEMPLATE_DIR = Path("templates")
OUTPUT_DIR = Path("docs")


def _parse_date(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _summary(markdown_text: str, limit: int = 150) -> str:
    """生成首页纯文本摘要，避免截断 HTML 标签。"""
    plain = markdown_text.replace("{{affiliate_link}}", "")
    plain = re.sub(r"[\[\]#*_>`~()-]", " ", plain)
    plain = " ".join(plain.split())
    return plain if len(plain) <= limit else plain[:limit].rstrip() + "…"


def load_posts(content_dir: Path = CONTENT_DIR) -> list[dict[str, object]]:
    posts: list[dict[str, object]] = []
    if not content_dir.exists():
        return posts
    for path in content_dir.glob("*.md"):
        try:
            document = frontmatter.load(path)
            required = ("title", "date", "category", "original_link")
            missing = [key for key in required if not document.get(key)]
            if missing:
                LOGGER.warning("跳过 %s：缺少 front matter 字段 %s", path, ", ".join(missing))
                continue
            date = _parse_date(document["date"])
            slug = str(document.get("slug") or path.stem)
            posts.append(
                {
                    "title": str(document["title"]),
                    "date": date,
                    "date_text": date.strftime("%Y-%m-%d"),
                    "category": str(document["category"]),
                    "original_link": str(document["original_link"]),
                    "slug": slug,
                    "url": f"posts/{quote(slug)}.html",
                    "body": document.content,
                    "summary": _summary(document.content),
                }
            )
        except (OSError, ValueError, TypeError) as exc:
            LOGGER.warning("跳过无法读取的文章 %s：%s", path, exc)
    return sorted(posts, key=lambda item: item["date"], reverse=True)


def build_site(
    content_dir: Path = CONTENT_DIR,
    template_dir: Path = TEMPLATE_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> int:
    """清理并完整重建 docs，返回有效文章数量。"""
    posts = load_posts(content_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "posts").mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    site_name = os.getenv("SITE_NAME") or "科技工具推荐"
    site_description = os.getenv("SITE_DESCRIPTION") or "每天发现值得关注的科技产品与效率工具"
    site_url = (os.getenv("SITE_URL") or "http://localhost:8000").rstrip("/")
    affiliate_link = os.getenv("AFFILIATE_LINK", "").strip()
    common = {
        "site_name": site_name,
        "site_description": site_description,
        "site_url": site_url,
    }

    post_template = env.get_template("post.html")
    for post in posts:
        target_link = affiliate_link or str(post["original_link"])
        body = str(post["body"]).replace("{{affiliate_link}}", target_link)
        # 先转义原始 HTML，再解析 Markdown，阻止生成内容注入脚本。
        post["html"] = Markup(markdown.markdown(str(escape(body)), extensions=["extra", "sane_lists"]))
        rendered = post_template.render(post=post, **common)
        (output_dir / str(post["url"])).write_text(rendered, encoding="utf-8")

    index_html = env.get_template("index.html").render(posts=posts[:10], **common)
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    rss_posts = []
    for post in posts[:20]:
        rss_post = dict(post)
        rss_post["absolute_url"] = f"{site_url}/{post['url']}"
        rss_post["pub_date"] = format_datetime(post["date"])
        rss_posts.append(rss_post)
    # 使用内容日期而非构建时钟，保证没有新文章时输出可重复，不制造空提交。
    rss_build_date = posts[0]["date"] if posts else datetime(1970, 1, 1, tzinfo=timezone.utc)
    rss_xml = env.get_template("rss.xml").render(
        posts=rss_posts,
        build_date=format_datetime(rss_build_date),
        **common,
    )
    (output_dir / "rss.xml").write_text(rss_xml, encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    cname = os.getenv("CUSTOM_DOMAIN", "").strip()
    if cname:
        (output_dir / "CNAME").write_text(cname + "\n", encoding="utf-8")
    LOGGER.info("网站构建完成：%d 篇文章，输出到 %s", len(posts), output_dir)
    return len(posts)
