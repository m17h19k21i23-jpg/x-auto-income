"""
normalize.py — 生データを標準 Item 形式に変換・検証する。

除外条件:
- url が空 / 無効
- expires_at が過去
- title が空
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# URL バリデーション（http / https のみ）
_URL_RE = re.compile(r"^https?://[^\s/$.?#].\S*$", re.IGNORECASE)


class Item(TypedDict):
    id: str                     # URL の SHA-256（先頭 16 hex）
    title: str
    url: str                    # 公式 URL（必須）
    source: str
    summary: str
    value: str                  # 例: "LTD $49" / "無料" / "$79（87%OFF）"
    original_value: str         # 元値表示用（例: "$588/年"）空文字の場合は非表示
    use_case: str               # 用途ラベル（例: "AI文章生成" / "SEO分析"）
    target_user: str            # 対象ユーザー（例: "EC / サポート担当向け"）
    category: str               # ai_tool / saas / game / other
    expires_at: str | None      # ISO 8601 UTC またはNone
    score: float                # score.py で設定（初期値 0.0）
    collected_at: str           # ISO 8601 UTC
    posted_at: str | None       # ISO 8601 UTC またはNone


def _item_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_expires(raw: Any) -> str | None:
    """文字列・datetime・None を受け取り、ISO 8601 UTC 文字列を返す。"""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        raw_str = str(raw).strip().rstrip("Z")
        # Python 3.10 以前でも動くように手動で処理
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw_str[:len(fmt) + (3 if "T" in fmt else 0) + 3], fmt)
                break
            except ValueError:
                continue
        else:
            try:
                dt = datetime.fromisoformat(raw_str)
            except Exception:
                logger.warning("expires_at parse failed: %r", raw)
                return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_expired(expires_at: str | None) -> bool:
    if expires_at is None:
        return False
    try:
        dt = datetime.fromisoformat(expires_at.rstrip("Z")).replace(tzinfo=timezone.utc)
        return dt <= datetime.now(timezone.utc)
    except Exception:
        return False


def normalize(raw: dict[str, Any]) -> Item | None:
    """
    1 件の生データを Item に変換する。
    除外すべき場合は None を返す。
    """
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()

    # 必須フィールドチェック
    if not title:
        logger.debug("Dropped: empty title — %r", raw)
        return None

    if not url or not _URL_RE.match(url):
        logger.debug("Dropped: invalid/missing url — %r", title)
        return None

    expires_at = _parse_expires(raw.get("expires_at"))

    if _is_expired(expires_at):
        logger.debug("Dropped: expired — %r", title)
        return None

    summary = (raw.get("summary") or "").strip()[:200]
    value = (raw.get("value") or "").strip()
    original_value = (raw.get("original_value") or "").strip()
    use_case = (raw.get("use_case") or "").strip()
    target_user = (raw.get("target_user") or "").strip()
    category = (raw.get("category") or "other").strip().lower()
    source = (raw.get("source") or "unknown").strip()

    return Item(
        id=_item_id(url),
        title=title,
        url=url,
        source=source,
        summary=summary,
        value=value,
        original_value=original_value,
        use_case=use_case,
        target_user=target_user,
        category=category,
        expires_at=expires_at,
        score=0.0,
        collected_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        posted_at=None,
    )


def normalize_all(
    raw_items: list[dict[str, Any]],
) -> tuple[list[Item], dict[str, int]]:
    """
    複数の生データを正規化して返す。

    Returns:
        (valid_items, stats) のタプル。
        stats は除外理由ごとのカウント。
    """
    valid: list[Item] = []
    stats = {"total": len(raw_items), "valid": 0, "dropped": 0}

    for raw in raw_items:
        item = normalize(raw)
        if item is not None:
            valid.append(item)
            stats["valid"] += 1
        else:
            stats["dropped"] += 1

    logger.info(
        "Normalize: %d -> %d valid, %d dropped",
        stats["total"],
        stats["valid"],
        stats["dropped"],
    )
    return valid, stats
