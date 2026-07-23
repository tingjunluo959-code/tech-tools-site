"""读取 Markdown 并构建英文主站与中文 /zh/ 镜像。"""

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
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _summary(markdown_text: str, limit: int = 150) -> str:
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
            language = str(document.get("lang") or "zh").lower()
            if language not in {"zh", "en"}:
                language = "zh"
            posts.append({
                "title": str(document["title"]), "date": date, "date_text": date.strftime("%Y-%m-%d"),
                "category": str(document["category"]), "original_link": str(document["original_link"]),
                "slug": slug, "lang": language, "translation_slug": str(document.get("translation_slug") or slug),
                "body": document.content, "summary": _summary(document.content), "source_path": path,
            })
        except (OSError, ValueError, TypeError) as exc:
            LOGGER.warning("跳过无法读取的文章 %s：%s", path, exc)
    return sorted(posts, key=lambda item: item["date"], reverse=True)


def _render_language(posts: list[dict[str, object]], language: str, env: Environment, output_dir: Path, common: dict[str, str], affiliate_link: str, force_root: bool = False) -> None:
    """渲染一种语言的首页、文章页和 RSS。"""
    is_zh = language == "zh"
    prefix = output_dir / "zh" if is_zh and not force_root else output_dir
    posts_dir = prefix / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    selected = [dict(post) for post in posts if post["lang"] == language]
    # 只有旧数据时，根路径仍保留可访问内容；双语数据出现后根路径优先英文。
    for post in selected:
        post["url"] = f"posts/{quote(str(post['slug']))}.html"
    other = "en" if is_zh else "zh"
    other_posts = {str(p["translation_slug"]): p for p in posts if p["lang"] == other}
    template = env.get_template("post.html")
    for post in selected:
        target_link = affiliate_link or str(post["original_link"])
        body = str(post["body"]).replace("{{affiliate_link}}", target_link)
        post["html"] = Markup(markdown.markdown(str(escape(body)), extensions=["extra", "sane_lists"]))
        counterpart = other_posts.get(str(post["translation_slug"]))
        context = dict(common)
        context.update({"language": language, "home_href": "../index.html", "rss_href": "../rss.xml", "language_label": "中文" if is_zh else "English", "switch_href": f"../posts/{quote(str(counterpart['slug']))}.html" if is_zh and counterpart else (f"../zh/posts/{quote(str(counterpart['slug']))}.html" if counterpart else "../zh/index.html" if not is_zh else "../index.html")})
        (posts_dir / f"{quote(str(post['slug']))}.html").write_text(template.render(post=post, **context), encoding="utf-8")

    rss_posts = []
    for post in selected[:20]:
        item = dict(post)
        base = common["site_url"]
        item["absolute_url"] = f"{base}/{'zh/' if is_zh else ''}{item['url']}"
        item["pub_date"] = format_datetime(item["date"])
        rss_posts.append(item)
    build_date = selected[0]["date"] if selected else datetime(1970, 1, 1, tzinfo=timezone.utc)
    rss_context = dict(common)
    rss_context.update({"language": language, "language_code": "zh-CN" if is_zh else "en", "rss_path": "zh/rss.xml" if is_zh else "rss.xml"})
    (prefix / "rss.xml").write_text(env.get_template("rss.xml").render(posts=rss_posts, build_date=format_datetime(build_date), **rss_context), encoding="utf-8")

    index_context = dict(common)
    index_context.update({"language": language, "home_href": "index.html", "rss_href": "rss.xml", "language_label": "中文" if is_zh else "English", "switch_href": "../index.html" if is_zh else "zh/index.html"})
    (prefix / "index.html").write_text(env.get_template("index.html").render(posts=selected[:10], **index_context), encoding="utf-8")


def build_site(content_dir: Path = CONTENT_DIR, template_dir: Path = TEMPLATE_DIR, output_dir: Path = OUTPUT_DIR) -> int:
    posts = load_posts(content_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"]), trim_blocks=True, lstrip_blocks=True)
    site_name = os.getenv("SITE_NAME") or "Tech Tools Worth Watching"
    site_description = os.getenv("SITE_DESCRIPTION") or "A daily, source-aware look at new tools from Product Hunt."
    site_url = (os.getenv("SITE_URL") or "http://localhost:8000").rstrip("/")
    common = {"site_name": site_name, "site_description": site_description, "site_url": site_url}
    affiliate_link = os.getenv("AFFILIATE_LINK", "").strip()

    languages = {str(post["lang"]) for post in posts}
    if "en" not in languages and "zh" in languages:
        # 兼容旧单语内容：根路径暂时展示中文，同时仍生成 /zh/ 镜像。
        _render_language(posts, "zh", env, output_dir, common, affiliate_link, force_root=True)
    else:
        _render_language(posts, "en", env, output_dir, common, affiliate_link)
    _render_language(posts, "zh", env, output_dir, common, affiliate_link)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    cname = os.getenv("CUSTOM_DOMAIN", "").strip()
    if cname:
        (output_dir / "CNAME").write_text(cname + "\n", encoding="utf-8")
    LOGGER.info("网站构建完成：%d 篇文章，输出到 %s", len(posts), output_dir)
    return len(posts)
