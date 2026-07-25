"""基于证据的场景化写作提示词。

不要求模型伪装亲测；可把截图和定价快照作为“观察材料”，并要求标注推断边界。
"""

from __future__ import annotations

import json


def build_experience_prompt(product: dict[str, object], language: str = "en") -> str:
    evidence = {
        "product": product.get("title", ""),
        "official_description": product.get("description", ""),
        "category": product.get("category", ""),
        "official_url": product.get("official_url") or product.get("link", ""),
        "link_status": product.get("link_status", {}),
        "pricing_snapshot": product.get("pricing", {}),
        "screenshot_available": bool(product.get("screenshot")),
    }
    if language == "zh":
        return f"""你是一名严谨的科技产品分析师。以下是公开资料和自动化观察结果：\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\n请用中文 Markdown 写一篇场景化分析：提出 3 个真实用户可能遇到的业务场景，说明这些场景为什么可能适用，并基于截图/公开功能讨论界面信息架构与学习成本。严禁声称亲自使用、编造未提供的功能、价格、体验或评价；主观判断必须使用“从公开页面观察”“可能”等限定语。单独列出“待核实信息”，提醒读者以官网为准。"""
    return f"""You are a careful technology product analyst. The following is public source material and automated observation data:\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n\nWrite a readable Markdown analysis with three realistic business scenarios, explaining why each may fit. Discuss visible information architecture and likely learning curve only as observations or clearly marked inferences. Never claim first-hand use, and never invent features, prices, reviews, or outcomes. Include a short 'Verify before subscribing' section and tell readers to confirm current details on the official site."""
