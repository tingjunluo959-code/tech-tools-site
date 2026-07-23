"""GitHub Actions 工作流的关键配置回归测试。"""

import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_daily_schedule_secret_and_write_permission(self):
        workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '0 0 * * *'", workflow)
        self.assertIn("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}", workflow)
        self.assertIn("CONTENT_MODE: ${{ vars.CONTENT_MODE || 'template' }}", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("run: python main.py", workflow)
        self.assertIn("git push", workflow)

    def test_workflow_has_no_known_mojibake_markers(self):
        workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
        for marker in ("ç§", "æŠ", "Ã", "¿Æ"):
            self.assertNotIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
