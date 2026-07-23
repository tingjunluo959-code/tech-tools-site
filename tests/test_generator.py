"""generator 的重试与 Markdown 落盘测试。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import frontmatter

from generator import (
    AFFILIATE_PLACEHOLDER,
    _chinese_character_count,
    generate_article,
    generate_template_article,
)


class _Message:
    content = "## 功能概览\n\n" + ("这" * 420)


class _Choice:
    message = _Message()


class _Response:
    choices = [_Choice()]


class _Completions:
    def __init__(self, fail_count=0):
        self.fail_count = fail_count
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("temporary failure")
        return _Response()


class _Chat:
    def __init__(self, completions):
        self.completions = completions


class _Client:
    def __init__(self, fail_count=0):
        self.completions = _Completions(fail_count)
        self.chat = _Chat(self.completions)


PRODUCT = {
    "title": "Example Tool",
    "link": "https://example.com/product",
    "description": "A useful tool",
    "category": "开发工具",
}


class GeneratorTests(unittest.TestCase):
    def test_local_template_needs_no_api_and_meets_length(self):
        article = generate_template_article(PRODUCT)
        self.assertIn("产品速览", article)
        self.assertIn(PRODUCT["title"], article)
        self.assertIn(PRODUCT["description"], article)
        self.assertIn(AFFILIATE_PLACEHOLDER, article)
        self.assertTrue(400 <= _chinese_character_count(article) <= 600)

    def test_retries_twice_then_writes_front_matter(self):
        client = _Client(fail_count=2)
        with tempfile.TemporaryDirectory() as temp, patch("generator.time.sleep"):
            path = generate_article(PRODUCT, client=client, content_dir=Path(temp))
            self.assertIsNotNone(path)
            self.assertEqual(client.completions.calls, 3)
            post = frontmatter.load(path)
            self.assertEqual(post["original_link"], PRODUCT["link"])
            self.assertEqual(post["category"], "开发工具")
            self.assertIn(AFFILIATE_PLACEHOLDER, post.content)

    def test_returns_none_after_three_failures(self):
        client = _Client(fail_count=3)
        with tempfile.TemporaryDirectory() as temp, patch("generator.time.sleep"):
            path = generate_article(PRODUCT, client=client, content_dir=Path(temp))
        self.assertIsNone(path)
        self.assertEqual(client.completions.calls, 3)

    def test_rejects_article_outside_required_length(self):
        client = _Client()
        client.chat.completions.create = lambda **_kwargs: type(
            "Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "太短"})()})()]}
        )()
        with tempfile.TemporaryDirectory() as temp, patch("generator.time.sleep"):
            path = generate_article(PRODUCT, client=client, content_dir=Path(temp))
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
