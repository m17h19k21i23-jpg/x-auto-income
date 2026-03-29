"""
render_site.py — Jinja2 テンプレートから site/index.html を生成する。

MONETIZATION_ENABLED=true の場合のみ収益リンクスロットを表示する。
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.normalize import Item

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
SITE_DIR = Path(__file__).parent.parent / "site"

FEATURED_COUNT = 3
MAX_ALL_DISPLAYED = 12


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
        local_str = dt.strftime("%m/%d")
        return f"あと{days}日（{local_str}）"
    except Exception:
        return expires_at


def _featured_score(item: dict) -> float:
    """
    おすすめ選出スコアを計算する。
    期限が近い / 値引き率が大きい / LTD を優先する。
    """
    score = item.get("score", 0.0)
    val = (item.get("value") or "").lower()
    expires_label = item.get("expires_label", "")

    # LTD ボーナス
    if "ltd" in val or "lifetime" in val or "買い切り" in val:
        score += 0.3

    # 高値引きボーナス
    m = re.search(r"(\d+)%", val)
    if m:
        pct = int(m.group(1))
        score += min(pct / 150.0, 0.4)

    # 期限迫迫ボーナス（7日以内）
    if "時間" in expires_label:
        score += 0.5
    elif "あと" in expires_label and "日" in expires_label:
        dm = re.search(r"あと(\d+)日", expires_label)
        if dm:
            days = int(dm.group(1))
            if days <= 3:
                score += 0.4
            elif days <= 7:
                score += 0.2

    return score


def _get_recommendation_reason(item: dict) -> str:
    """おすすめ理由のラベルを返す（締切近い / 値引き大 / 人気カテゴリ）。"""
    expires_label = item.get("expires_label", "")
    val = (item.get("value") or "").lower()

    # 締切が3日以内
    if "時間" in expires_label:
        return "締切近い"
    dm = re.search(r"あと(\d+)日", expires_label)
    if dm and int(dm.group(1)) <= 3:
        return "締切近い"

    # 値引き率 70% 以上 or LTD
    m = re.search(r"(\d+)%", val)
    if m and int(m.group(1)) >= 70:
        return "値引き大"
    if "ltd" in val or "lifetime" in val or "買い切り" in val:
        return "値引き大"

    return "人気カテゴリ"


def _select_featured(active_items: list[dict]) -> list[dict]:
    """
    おすすめ3件を選ぶ。
    基準: 期限が近い・値引きが強い・用途が被りすぎない。
    """
    scored = sorted(active_items, key=_featured_score, reverse=True)
    selected: list[dict] = []
    used_use_cases: set[str] = set()
    selected_ids: set[str] = set()

    # 用途多様性を保ちながら上位から選出
    for item in scored:
        if len(selected) >= FEATURED_COUNT:
            break
        use_case = item.get("use_case", "")
        if use_case and use_case in used_use_cases:
            continue
        selected.append({**item, "recommendation_reason": _get_recommendation_reason(item)})
        used_use_cases.add(use_case)
        selected_ids.add(item.get("id", ""))

    # 用途多様性で足りない場合はスコア順に補充
    if len(selected) < FEATURED_COUNT:
        for item in scored:
            if len(selected) >= FEATURED_COUNT:
                break
            if item.get("id", "") not in selected_ids:
                selected.append({**item, "recommendation_reason": _get_recommendation_reason(item)})
                selected_ids.add(item.get("id", ""))

    return selected


def render(
    items: list[Item],
    dry_run: bool = False,
) -> str:
    """
    site/index.html を生成してパスを返す。
    dry_run=True の場合はファイルに書き出さず生成内容を返す。
    """
    monetization = os.getenv("MONETIZATION_ENABLED", "false").lower() == "true"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 終了済みアイテムは除外
    active_items = []
    for item in items:
        label = _expires_label(item.get("expires_at"))
        if label == "終了済み":
            continue
        active_items.append({**item, "expires_label": label})

    # スコア降順でソート
    active_items.sort(key=lambda i: i.get("score", 0), reverse=True)

    # おすすめ3件を選出
    featured_items = _select_featured(active_items)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")

    displayed_items = active_items[:MAX_ALL_DISPLAYED]
    hidden_count = max(0, len(active_items) - MAX_ALL_DISPLAYED)

    html = template.render(
        items=active_items,
        displayed_items=displayed_items,
        hidden_count=hidden_count,
        featured_items=featured_items,
        updated_at=now_str,
        total=len(active_items),
        monetization=monetization,
    )

    if dry_run:
        logger.info("[dry-run] Site HTML generated (%d bytes)", len(html))
        return html

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SITE_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    logger.info("Site rendered -> %s (%d items)", out_path, len(active_items))
    return html
