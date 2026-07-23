"""静态站构建的集成测试。"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import frontmatter

from build import build_site


class BuildTests(unittest.TestCase):
    def test_builds_latest_ten_and_safe_post_html(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / "content"
            output = root / "docs"
            content.mkdir()
            for index in range(11):
                post = frontmatter.Post(
                    f"正文 {index}\n\n[了解更多]({{{{affiliate_link}}}})\n\n<script>alert(1)</script>"
                )
                post.metadata.update(
                    {
                        "title": f"文章 {index}",
                        "date": datetime(2026, 1, index + 1, tzinfo=timezone.utc).isoformat(),
                        "category": "测试",
                        "original_link": f"https://example.com/{index}",
                        "slug": f"post-{index}",
                    }
                )
                (content / f"post-{index}.md").write_text(frontmatter.dumps(post), encoding="utf-8")

            env = {
                "SITE_URL": "https://site.example",
                "AFFILIATE_LINK": "https://affiliate.example/ref",
            }
            with patch.dict(os.environ, env, clear=False):
                count = build_site(content_dir=content, template_dir=Path("templates"), output_dir=output)

            self.assertEqual(count, 11)
            index_html = (output / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("文章 0</a>", index_html)
            self.assertIn("文章 10</a>", index_html)
            post_html = (output / "posts/post-10.html").read_text(encoding="utf-8")
            self.assertIn("https://affiliate.example/ref", post_html)
            self.assertNotIn("<script>alert(1)</script>", post_html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", post_html)
            ET.parse(output / "rss.xml")
            self.assertTrue((output / ".nojekyll").exists())


if __name__ == "__main__":
    unittest.main()
