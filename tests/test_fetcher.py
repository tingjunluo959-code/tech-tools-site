"""fetcher 的离线确定性测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fetcher import fetch_new_products, mark_processed, parse_feed, product_id


ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Example Tool</title>
    <link rel="alternate" href="https://example.com/product" />
    <content type="html">&lt;p&gt;Useful &amp;amp; fast.&lt;/p&gt;&lt;p&gt;&lt;a href="x"&gt;Discussion&lt;/a&gt;&lt;/p&gt;</content>
  </entry>
  <entry><title>Missing link</title></entry>
</feed>"""

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><item>
  <title>RSS Tool</title><link>https://example.com/rss</link>
  <description>&lt;p&gt;RSS description&lt;/p&gt;</description><category>开发工具</category>
</item></channel></rss>"""


class FetcherTests(unittest.TestCase):
    def test_parse_atom_and_default_missing_category(self):
        products = parse_feed(ATOM)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["description"], "Useful & fast.")
        self.assertEqual(products[0]["category"], "未分类")

    def test_parse_rss_category(self):
        product = parse_feed(RSS)[0]
        self.assertEqual(product["title"], "RSS Tool")
        self.assertEqual(product["category"], "开发工具")

    def test_processed_product_is_filtered(self):
        with tempfile.TemporaryDirectory() as temp:
            processed = Path(temp) / "processed.txt"
            mark_processed("https://example.com/product", processed)
            with patch("fetcher._download_feed", return_value=ATOM):
                products = fetch_new_products(processed, feed_url="https://feed.example/rss")
            self.assertEqual(products, [])
            self.assertIn(product_id("https://example.com/product"), processed.read_text(encoding="utf-8"))

    def test_malformed_xml_is_reported(self):
        with self.assertRaisesRegex(ValueError, "Feed XML 解析失败"):
            parse_feed("<not-closed>")


if __name__ == "__main__":
    unittest.main()
