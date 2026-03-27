"""
dedupe.py — state.json を使って投稿済みアイテムを除外する。

state.json スキーマ:
{
  "version": 1,
  "posted_ids": ["abc123", ...],
  "last_run": "2026-01-01T00:00:00Z" | null,
  "last_post": "2026-01-01T00:00:00Z" | null,
  "stats": { ... }
}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.normalize import Item

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent.parent / "state" / "state.json"


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    """state.json を読み込む。存在しない場合は初期状態を返す。"""
    if not path.exists():
        logger.warning("state.json not found at %s, starting fresh", path)
        return _empty_state()
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load state.json: %s — starting fresh", exc)
        return _empty_state()


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    """state.json を保存する（dry-run 時は呼ばない）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    logger.debug("State saved to %s", path)


def filter_new(
    items: list[Item],
    state: dict[str, Any],
) -> tuple[list[Item], int]:
    """
    投稿済み ID を除いた新規アイテムのみを返す。

    Returns:
        (new_items, duplicate_count)
    """
    posted_ids: set[str] = set(state.get("posted_ids", []))
    new_items = [i for i in items if i["id"] not in posted_ids]
    duplicates = len(items) - len(new_items)

    if duplicates:
        logger.info("Dedupe: %d duplicates removed", duplicates)

    return new_items, duplicates


def mark_posted(
    state: dict[str, Any],
    items: list[Item],
) -> dict[str, Any]:
    """
    投稿済みアイテムの ID を state に追記して返す（保存はしない）。
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    posted_ids: list[str] = state.get("posted_ids", [])
    for item in items:
        if item["id"] not in posted_ids:
            posted_ids.append(item["id"])

    state["posted_ids"] = posted_ids
    state["last_post"] = now

    stats = state.setdefault("stats", {})
    stats["total_posted"] = stats.get("total_posted", 0) + len(items)

    return state


def update_run_stats(
    state: dict[str, Any],
    collected: int = 0,
    filtered_expired: int = 0,
    filtered_score: int = 0,
    filtered_dup: int = 0,
) -> dict[str, Any]:
    """実行ごとの集計を state に反映する（保存はしない）。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state["last_run"] = now

    stats = state.setdefault("stats", {})
    stats["total_collected"] = stats.get("total_collected", 0) + collected
    stats["total_filtered_expired"] = (
        stats.get("total_filtered_expired", 0) + filtered_expired
    )
    stats["total_filtered_low_score"] = (
        stats.get("total_filtered_low_score", 0) + filtered_score
    )
    stats["total_filtered_duplicate"] = (
        stats.get("total_filtered_duplicate", 0) + filtered_dup
    )
    return state


def _empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "posted_ids": [],
        "last_run": None,
        "last_post": None,
        "stats": {
            "total_collected": 0,
            "total_posted": 0,
            "total_filtered_expired": 0,
            "total_filtered_low_score": 0,
            "total_filtered_duplicate": 0,
        },
    }
