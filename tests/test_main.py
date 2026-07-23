"""主流程对部分失败和全部失败的处理测试。"""

import os
import unittest
from pathlib import Path
from unittest.mock import call, patch

import main


PRODUCTS = [
    {"title": "A", "link": "https://example.com/a", "description": "a", "category": "测试"},
    {"title": "B", "link": "https://example.com/b", "description": "b", "category": "测试"},
]


class MainTests(unittest.TestCase):
    @patch("main.build_site", return_value=1)
    @patch("main.mark_processed")
    @patch("main.generate_article", side_effect=[Path("a.md"), None])
    @patch("main.fetch_new_products", return_value=PRODUCTS)
    def test_partial_success_marks_only_successful_product(
        self, _fetch, _generate, mark, _build
    ):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "MAX_PRODUCTS_PER_RUN": "0"}, clear=False):
            result = main.main()
        self.assertEqual(result, 0)
        self.assertEqual(mark.call_count, 1)
        self.assertEqual(mark.call_args, call("https://example.com/a", Path("processed_ids.txt")))

    @patch("main.build_site", return_value=0)
    @patch("main.mark_processed")
    @patch("main.generate_article", return_value=None)
    @patch("main.fetch_new_products", return_value=PRODUCTS[:1])
    def test_all_generation_failures_return_failure(self, _fetch, _generate, mark, _build):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "MAX_PRODUCTS_PER_RUN": "0"}, clear=False):
            result = main.main()
        self.assertEqual(result, 1)
        mark.assert_not_called()

    @patch("main.fetch_new_products", return_value=PRODUCTS[:1])
    def test_missing_api_key_returns_failure(self, _fetch):
        with patch.dict(
            os.environ,
            {"CONTENT_MODE": "openai", "MAX_PRODUCTS_PER_RUN": "0"},
            clear=False,
        ):
            os.environ.pop("OPENAI_API_KEY", None)
            result = main.main()
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
