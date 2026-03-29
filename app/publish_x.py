"""
publish_x.py — X（旧Twitter）に AI / SaaS / 自動化ツール deals 情報を投稿する。

テンプレート:
  - SALE  (値下げ): 割引価格のセール情報
  - LTD   (買い切り): ライフタイムディール
  - TRIAL (無料トライアル): 無料で試せるプラン

投稿前チェック:
  1. POST_ENABLED=true か確認
  2. 重複 ID チェック（state 参照）
  3. URL 有無チェック
  4. 文字数チェック（URL は t.co の 23 文字として計算）
  5. テンプレートの連続使用チェック（同じテンプレート 3 連続禁止）
"""
from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timezone
from typing import Any

from app.normalize import Item

logger = logging.getLogger(__name__)

MAX_TWEET_LENGTH = 280
T_CO_LENGTH = 23  # X の URL 短縮後の文字数

# 投稿テンプレート（値下げ・LTD・無料トライアルで使い分け）
_TEMPLATE_SALE = (
    "【AI/SaaS値下げ】\n"
    "{title}\n\n"
    "割引価格: {value}\n"
    "期限: {expires_label}\n"
    "詳細: {url}"
)
_TEMPLATE_LTD = (
    "【買い切りLTD】\n"
    "{title}\n\n"
    "{value} でずっと使える！\n"
    "期限: {expires_label}\n"
    "詳細: {url}"
)
_TEMPLATE_TRIAL = (
    "【無料トライアル】\n"
    "{title}\n\n"
    "今すぐ無料で試せます。\n"
    "期限: {expires_label}\n"
    "詳細: {url}"
)
_TEMPLATES = [_TEMPLATE_SALE, _TEMPLATE_LTD, _TEMPLATE_TRIAL]


def _count_tweet_length(text: str, url: str) -> int:
    """
    X の文字数ルールに従った文字数を計算する。
    URL は t.co 短縮後の長さ（23文字）として扱う。
    """
    # テンプレート内の URL を仮の文字列に置換して計算
    text_without_url = text.replace(url, "")
    return len(text_without_url) + T_CO_LENGTH


def _build_tweet(item: Item, template_idx: int) -> str:
    """
    アイテムの value / summary に応じてテンプレートを選択し投稿テキストを生成する。

    選択ロジック:
      - value に "LTD" / "lifetime" / "買い切り" を含む → LTD テンプレート
      - value が空 / "無料" / "trial" を含む → 無料トライアルテンプレート
      - それ以外 (% OFF / 価格付き) → 値下げテンプレート

    template_idx は _select_template との互換性のために受け取るが、
    実際のテンプレート選択はアイテムの value に基づく。
    """
    value = (item.get("value") or "").strip()
    value_lower = value.lower()
    summary_lower = (item.get("summary") or "").lower()
    combined = value_lower + " " + summary_lower

    if "ltd" in value_lower or "lifetime" in combined or "買い切り" in combined:
        tpl = _TEMPLATE_LTD
    elif (
        not value
        or "無料" in value
        or "free" in value_lower
        or "0円" in value
        or "trial" in combined
        or "トライアル" in combined
    ):
        tpl = _TEMPLATE_TRIAL
    else:
        tpl = _TEMPLATE_SALE

    expires_label = item.get("expires_label") or item.get("expires_at") or "期限未定"

    text = tpl.format(
        title=item["title"],
        value=value or "無料",
        expires_label=expires_label,
        url=item["url"],
    )
    return text


def _select_template(
    used_templates: list[int],
    total_templates: int = len(_TEMPLATES),
) -> int:
    """
    直近 3 回使ったテンプレート以外からランダムに選ぶ。
    used_templates は最近使用したインデックスのリスト（先頭が最新）。
    """
    recent = set(used_templates[:3])
    candidates = [i for i in range(total_templates) if i not in recent]
    if not candidates:
        candidates = list(range(total_templates))
    return random.choice(candidates)


class XPublisher:
    def __init__(self) -> None:
        self.api_key = os.getenv("X_API_KEY", "")
        self.api_secret = os.getenv("X_API_SECRET", "")
        self.access_token = os.getenv("X_ACCESS_TOKEN", "")
        self.access_secret = os.getenv("X_ACCESS_SECRET", "")
        self.post_enabled = os.getenv("POST_ENABLED", "false").lower() == "true"
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import tweepy  # type: ignore
            self._client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
            )
            return self._client
        except ImportError:
            raise RuntimeError("tweepy がインストールされていません: pip install tweepy")

    def validate(self, item: Item) -> list[str]:
        """投稿前バリデーション。エラーメッセージのリストを返す（空=OK）。"""
        errors: list[str] = []

        if not item.get("url"):
            errors.append("url が空")
            return errors

        text = _build_tweet(item, 0)
        length = _count_tweet_length(text, item["url"])
        if length > MAX_TWEET_LENGTH:
            errors.append(f"文字数超過: {length}/{MAX_TWEET_LENGTH}")

        return errors

    def post(
        self,
        item: Item,
        template_idx: int,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        1 件を X に投稿する。

        Returns:
            {"success": bool, "tweet_id": str | None, "text": str, "error": str | None}
        """
        text = _build_tweet(item, template_idx)
        length = _count_tweet_length(text, item["url"])

        result: dict[str, Any] = {
            "success": False,
            "tweet_id": None,
            "text": text,
            "length": length,
            "error": None,
        }

        if length > MAX_TWEET_LENGTH:
            result["error"] = f"文字数超過: {length}/{MAX_TWEET_LENGTH}"
            logger.error("Post skipped: %s", result["error"])
            return result

        if dry_run:
            logger.info(
                "[dry-run] Would post (%d chars):\n%s", length, text
            )
            result["success"] = True
            result["tweet_id"] = "dry_run"
            return result

        if not self.post_enabled:
            logger.info("POST_ENABLED=false — skipping post: %s", item["title"])
            result["success"] = True
            result["tweet_id"] = "skipped"
            return result

        try:
            client = self._get_client()
            response = client.create_tweet(text=text)
            tweet_id = str(response.data["id"])
            result["success"] = True
            result["tweet_id"] = tweet_id
            logger.info(
                "Posted: tweet_id=%s title=%r (%d chars)",
                tweet_id,
                item["title"],
                length,
            )
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("Post failed for %r: %s", item["title"], exc)

        return result


def post_items(
    items: list[Item],
    max_posts: int = 3,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    複数アイテムを投稿する。

    Args:
        items: 投稿対象アイテム（スコア降順推奨）
        max_posts: 1 回の実行で投稿する最大件数
        dry_run: True の場合は実際に投稿しない

    Returns:
        各アイテムの投稿結果リスト
    """
    publisher = XPublisher()
    results: list[dict[str, Any]] = []
    used_templates: list[int] = []

    for item in items[:max_posts]:
        errors = publisher.validate(item)
        if errors:
            logger.warning("Validation failed for %r: %s", item["title"], errors)
            results.append(
                {
                    "item_id": item["id"],
                    "success": False,
                    "error": "; ".join(errors),
                }
            )
            continue

        tpl_idx = _select_template(used_templates)
        result = publisher.post(item, tpl_idx, dry_run=dry_run)
        result["item_id"] = item["id"]
        result["template_idx"] = tpl_idx
        results.append(result)

        if result["success"]:
            used_templates.insert(0, tpl_idx)

    return results
