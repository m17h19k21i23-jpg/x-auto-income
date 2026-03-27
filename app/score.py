"""
score.py — Item にスコアを付与し、閾値以下を除外する。

スコアリング基準（合計 1.0）:
  +0.30  価値の明確さ（"無料" / "¥X相当" / "%OFF" を含む）
  +0.25  期限が設定されている（希少性・緊急性）
  +0.20  カテゴリーボーナス（game/software は高め）
  +0.15  価値の大きさ（金額・割引率が大きい）
  +0.10  要約の充実度（summary が 30 文字以上）
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from app.normalize import Item

logger = logging.getLogger(__name__)

DEFAULT_MIN_SCORE: float = 0.5

_YEN_RE = re.compile(r"[¥￥][\d,]+")
_PCT_RE = re.compile(r"(\d+)\s*%\s*[Oo][Ff][Ff]|(\d+)\s*%\s*OFF|(\d+)%引き")
_FREE_RE = re.compile(r"無料|free|フリー|0円", re.IGNORECASE)

_CATEGORY_BONUS = {
    "game": 0.20,
    "software": 0.18,
    "service": 0.15,
    "other": 0.05,
}


def _score_value_clarity(value: str) -> float:
    """価値が数値または "無料" で明示されているか。"""
    if _FREE_RE.search(value):
        return 0.30
    if _YEN_RE.search(value):
        return 0.28
    if _PCT_RE.search(value):
        return 0.22
    if value.strip():
        return 0.10  # 何か書いてある
    return 0.0


def _score_value_magnitude(value: str) -> float:
    """価値の大きさ（金額・割引率）。"""
    # 無料は最大
    if _FREE_RE.search(value):
        return 0.15

    # 円額
    m = _YEN_RE.search(value)
    if m:
        try:
            amount = int(m.group().replace("¥", "").replace("￥", "").replace(",", ""))
            if amount >= 10000:
                return 0.15
            if amount >= 3000:
                return 0.12
            if amount >= 1000:
                return 0.08
            return 0.04
        except ValueError:
            pass

    # 割引率
    m2 = _PCT_RE.search(value)
    if m2:
        pct_str = m2.group(1) or m2.group(2) or m2.group(3) or "0"
        try:
            pct = int(pct_str)
            if pct >= 80:
                return 0.15
            if pct >= 50:
                return 0.12
            if pct >= 30:
                return 0.08
            return 0.04
        except ValueError:
            pass

    return 0.0


def _score_deadline(expires_at: str | None) -> float:
    """期限があるか、かつ直近か。"""
    if not expires_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(expires_at.rstrip("Z")).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_left = (dt - now).total_seconds() / 86400
        if days_left <= 1:
            return 0.25  # 24時間以内
        if days_left <= 3:
            return 0.23
        if days_left <= 7:
            return 0.20
        return 0.15
    except Exception:
        return 0.05


def _score_category(category: str) -> float:
    return _CATEGORY_BONUS.get(category, 0.05)


def _score_summary(summary: str) -> float:
    if len(summary) >= 30:
        return 0.10
    if len(summary) >= 10:
        return 0.05
    return 0.0


def score_item(item: Item) -> Item:
    """Item にスコアを付与して返す（in-place 変更）。"""
    s = (
        _score_value_clarity(item["value"])
        + _score_value_magnitude(item["value"])
        + _score_deadline(item["expires_at"])
        + _score_category(item["category"])
        + _score_summary(item["summary"])
    )
    item["score"] = round(min(s, 1.0), 4)
    return item


def score_and_filter(
    items: list[Item],
    min_score: float = DEFAULT_MIN_SCORE,
) -> tuple[list[Item], int]:
    """
    スコア付与 + 閾値フィルタリング。

    Returns:
        (passing_items, dropped_count)
    """
    scored = [score_item(item) for item in items]
    passing = [i for i in scored if i["score"] >= min_score]
    dropped = len(scored) - len(passing)

    if dropped:
        logger.info(
            "Score filter: %d items dropped (score < %.2f)", dropped, min_score
        )

    passing.sort(key=lambda i: i["score"], reverse=True)
    return passing, dropped
