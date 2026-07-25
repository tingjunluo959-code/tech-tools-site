"""按最近文章生成可检索的领域 Top 榜单。"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import frontmatter


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "tools"


def generate_rankings(content_dir: Path, days: int = 30, limit: int = 5) -> int:
    posts = []
    for path in content_dir.glob("*.md") if content_dir.exists() else []:
        try:
            post = frontmatter.load(path)
            if post.get("content_type") == "ranking" or post.get("lang") != "en":
                continue
            date = datetime.fromisoformat(str(post["date"]).replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            if date < datetime.now(timezone.utc) - timedelta(days=days):
                continue
            posts.append((date, post))
        except (OSError, TypeError, ValueError, KeyError):
            continue
    by_category: dict[str, list[tuple[datetime, frontmatter.Post]]] = {}
    for date, post in posts:
        by_category.setdefault(str(post.get("category") or "Tools"), []).append((date, post))
    created = 0
    for category, items in by_category.items():
        items.sort(key=lambda pair: pair[0], reverse=True)
        chosen = items[:limit]
        if len(chosen) < 3:
            continue
        digest = hashlib.sha256(category.encode("utf-8")).hexdigest()[:8]
        base = f"top-{_slug(category)}-{digest}"
        lines = [f"## Top tools in {category}", "", "A rolling shortlist based on recent Product Hunt coverage. Verify current features and pricing on each official page before deciding.", ""]
        for index, (_date, post) in enumerate(chosen, 1):
            lines.append(f"### {index}. [{post['title']}]({{{{affiliate_url|{post['original_link']}}}}})")
            lines.append("")
            lines.append(str(post.content).split("\n", 2)[0][:280])
            lines.append("")
        en = frontmatter.Post("\n".join(lines))
        ranking_date = chosen[0][0]
        en.metadata.update({"title": f"{ranking_date.year}: Top {len(chosen)} {category} Tools to Watch", "date": ranking_date.isoformat(timespec="seconds"), "category": category, "original_link": "https://www.producthunt.com/", "slug": base, "lang": "en", "translation_slug": base, "content_type": "ranking"})
        (content_dir / f"{base}-en.md").write_text(frontmatter.dumps(en), encoding="utf-8")
        zh_lines = [f"## {category} 工具观察榜", "", "本榜单按最近 Product Hunt 文章整理，仅用于发现候选工具。功能、价格、隐私与服务条款请以各产品官网为准。", ""]
        for index, (_date, post) in enumerate(chosen, 1):
            zh_lines.extend([f"### {index}. [{post['title']}]({{{{affiliate_url|{post['original_link']}}}}})", "", "这是近期值得继续观察的候选工具，建议先小范围试用。", ""])
        zh = frontmatter.Post("\n".join(zh_lines))
        zh.metadata.update({"title": f"{ranking_date.year} 年值得关注的 {len(chosen)} 个{category}工具", "date": en["date"], "category": category, "original_link": en["original_link"], "slug": base, "lang": "zh", "translation_slug": base, "content_type": "ranking"})
        (content_dir / f"{base}-zh.md").write_text(frontmatter.dumps(zh), encoding="utf-8")
        created += 1
    return created
