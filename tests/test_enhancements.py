"""富化模块的确定性单元测试；不访问真实官网或启动浏览器。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import frontmatter

from affiliate import build_affiliate_url
from build import build_site
from config import Settings
from history_monitor import apply_promotion_alert, update_history
from link_checker import check_url
from pricing_parser import parse_pricing_html
from rankings import generate_rankings
from screenshot import capture_screenshot


class EnhancementTests(unittest.TestCase):
    def test_pricing_parser_extracts_plans_and_promotion(self):
        html = """
        <section><h2>Free</h2><p>Free</p><ul><li>10 projects</li></ul></section>
        <section><h2>Pro</h2><p>$12 / month</p><ul><li>Unlimited projects</li></ul></section>
        <section><h2>Enterprise</h2><p>Contact us</p></section>
        <div>Free trial this week - up to 50% off</div>
        """
        plans, promotions = parse_pricing_html(html)
        self.assertGreaterEqual(len(plans), 2)
        self.assertEqual(plans[1]["plan"], "Pro")
        self.assertTrue(any(plan["recommended"] for plan in plans))
        self.assertTrue(any("trial" in item.lower() for item in promotions))

    @patch("link_checker.requests.head")
    def test_link_checker_marks_404_without_raising(self, head):
        head.return_value = Mock(status_code=404)
        result = check_url("https://example.com/missing", Settings(request_timeout=1))
        self.assertFalse(result.ok)
        self.assertEqual(result.status_code, 404)

    def test_affiliate_template_is_configurable_and_safe_fallback(self):
        settings = Settings(affiliate_id="abc 123", affiliate_link_template="https://partner.test/go?ref={affiliate_id}&url={url}")
        value = build_affiliate_url("https://example.com/a?x=1", settings)
        self.assertIn("abc%20123", value)
        self.assertIn("https%3A%2F%2Fexample.com%2Fa%3Fx%3D1", value)
        bad = Settings(affiliate_id="x", affiliate_link_template="{missing}")
        self.assertEqual(build_affiliate_url("https://example.com", bad), "https://example.com")

    def test_history_only_reports_new_promotions_and_alert_updates(self):
        with tempfile.TemporaryDirectory() as temp:
            history = Path(temp) / "history.json"
            pricing = {"plans": [{"plan": "Pro", "price": "$5"}], "promotions": ["Free trial"]}
            status = {"url": "https://example.com", "status_code": 200, "ok": True, "checked_at": "now"}
            self.assertEqual(update_history("p1", "https://example.com", pricing, status, history), ["Free trial"])
            self.assertEqual(update_history("p1", "https://example.com", pricing, {**status, "checked_at": "later"}, history), [])
            content = Path(temp) / "posts"
            content.mkdir()
            post = frontmatter.Post("body")
            post.metadata.update({"product_id": "p1", "title": "A", "date": "2026-01-01T00:00:00+00:00", "category": "Tools", "original_link": "https://example.com"})
            path = content / "a.md"
            path.write_text(frontmatter.dumps(post), encoding="utf-8")
            self.assertEqual(apply_promotion_alert(content, "p1", ["Free trial"]), 1)
            self.assertEqual(frontmatter.load(path)["promotion_alerts"], ["Free trial"])
            self.assertEqual(json.loads(history.read_text(encoding="utf-8"))["products"]["p1"]["promotions"], ["Free trial"])

    def test_build_renders_screenshot_pricing_alert_and_link_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / "content"
            assets = root / "assets" / "screenshots"
            content.mkdir(parents=True)
            assets.mkdir(parents=True)
            (assets / "p1.png").write_bytes(b"not-a-real-png")
            for lang, title in (("en", "Demo Tool"), ("zh", "演示工具")):
                post = frontmatter.Post("![shot]({{screenshot_path}})\n\nBody")
                post.metadata.update({
                    "title": title, "date": "2026-01-01T00:00:00+00:00", "category": "Tools", "original_link": "https://example.com",
                    "official_url": "https://example.com", "slug": "p1", "lang": lang, "translation_slug": "p1", "product_id": "p1",
                    "screenshot": "assets/screenshots/p1.png", "pricing": [{"plan": "Pro", "price": "$5", "features": ["10 projects"], "recommended": True}],
                    "promotion_alerts": ["Free trial"], "link_status": {"ok": False},
                })
                (content / f"p1-{lang}.md").write_text(frontmatter.dumps(post), encoding="utf-8")
            output = root / "docs"
            with patch.dict(os.environ, {"SITE_URL": "https://site.test", "AFFILIATE_LINK": "https://partner.test/ref"}, clear=False):
                build_site(content, Path("templates"), output, root / "assets")
            en = (output / "posts/p1.html").read_text(encoding="utf-8")
            zh = (output / "zh/posts/p1.html").read_text(encoding="utf-8")
            self.assertIn("assets/screenshots/p1.png", en)
            self.assertIn("../../assets/screenshots/p1.png", zh)
            self.assertIn("Free trial", en)
            self.assertIn("https://partner.test/ref", en)
            self.assertIn("unavailable", en.lower())

    def test_disabled_screenshot_is_a_safe_noop(self):
        self.assertIsNone(capture_screenshot("https://example.com", "p1", Settings(screenshot_enabled=False)))

    def test_generates_deterministic_bilingual_ranking_with_dynamic_links(self):
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            for index in range(5):
                post = frontmatter.Post(f"Overview for tool {index}")
                post.metadata.update({
                    "title": f"Tool {index}", "date": f"2026-07-{20 + index:02d}T00:00:00+00:00", "category": "AI",
                    "original_link": f"https://example.com/{index}", "slug": f"tool-{index}", "lang": "en", "translation_slug": f"tool-{index}", "content_type": "product",
                })
                (content / f"tool-{index}-en.md").write_text(frontmatter.dumps(post), encoding="utf-8")
            self.assertEqual(generate_rankings(content, days=30, limit=5), 1)
            rankings = list(content.glob("top-*-en.md"))
            self.assertEqual(len(rankings), 1)
            generated = frontmatter.load(rankings[0])
            self.assertEqual(generated["content_type"], "ranking")
            self.assertIn("{{affiliate_url|https://example.com/4}}", generated.content)
            before = rankings[0].read_text(encoding="utf-8")
            generate_rankings(content, days=30, limit=5)
            self.assertEqual(rankings[0].read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
