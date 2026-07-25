"""联盟链接构造。

不同联盟计划的参数规则不同，因此不假设一个 ID 能适用于所有官网；使用
AFFILIATE_LINK_TEMPLATE 时请自行提供合法模板，例如
`https://example.com/signup?ref={affiliate_id}`。"""

from __future__ import annotations

from urllib.parse import quote

from config import Settings


def build_affiliate_url(original_url: str, settings: Settings | None = None) -> str:
    settings = settings or Settings.from_env()
    if settings.affiliate_link:
        return settings.affiliate_link
    if settings.affiliate_link_template and settings.affiliate_id:
        try:
            return settings.affiliate_link_template.format(
                url=quote(original_url, safe=""),
                affiliate_id=quote(settings.affiliate_id, safe=""),
            )
        except (KeyError, ValueError):
            # 配置错误时回退官方链接，避免生成坏链接。
            return original_url
    return original_url
