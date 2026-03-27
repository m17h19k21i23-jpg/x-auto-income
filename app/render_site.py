"""
render_site.py — Jinja2 テンプレートから site/index.html を生成する。

MONETIZATION_ENABLED=true の場合のみ収益リンクスロットを表示する。
dry_run=True でも site/index.html は書き出す。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.normalize import Item

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
SITE_DIR = Path(__file__).parent.parent / "site"


def _expires_label(expires_at: str | None) -> str:
    """期限を日本語のラベルに変換する。"""
    if not expires_at:
        return "期限未定"
    try:
        dt = datetime.fromisoformat(expires_at.rstrip("Z")).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = dt - now
        total_seconds = int(delta.total_seconds())

        if total_seconds <= 0:
            return "終了済み"
        if total_seconds < 3600:
            mins = total_seconds // 60
            return f"あと{mins}分"
        if total_seconds < 86400:
            hours = total_seconds // 3600
            return f"あと{hours}時間"

        days = total_seconds // 86400
        local_str = dt.strftime("%m/%d %H:%M UTC")
        return f"あと{days}日（{local_str}）"
    except Exception:
        return expires_at


def render(
    items: list[Item],
    dry_run: bool = False,
) -> str:
    """
    site/index.html を生成し、HTML文字列を返す。
    dry_run=True でもファイルには書き出す。
    """
    monetization = os.getenv("MONETIZATION_ENABLED", "false").lower() == "true"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    active_items = []
    for item in items:
        label = _expires_label(item.get("expires_at"))
        if label == "終了済み":
            continue
        active_items.append({**item, "expires_label": label})

    active_items.sort(key=lambda i: i.get("score", 0), reverse=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")

    html = template.render(
        items=active_items,
        updated_at=now_str,
        total=len(active_items),
        monetization=monetization,
        dry_run=dry_run,
    )

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SITE_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")

    if dry_run:
        logger.info("[dry-run] Site rendered -> %s (%d items)", out_path, len(active_items))
    else:
        logger.info("Site rendered -> %s (%d items)", out_path, len(active_items))

    return html
