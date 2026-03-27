"""
collect.py — 公式ソースからお得情報を収集する。

各 Collector は collect() メソッドを実装し、生のdictリストを返す。
@register デコレーターで自動登録される。
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_REGISTRY: list[type[BaseCollector]] = []


def register(cls: type[BaseCollector]) -> type[BaseCollector]:
    """コレクターをグローバルレジストリに登録するデコレーター。"""
    _REGISTRY.append(cls)
    return cls


class BaseCollector:
    name: str = "base"
    REQUEST_TIMEOUT: int = 15

    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Epic Games — 無料ゲーム（公式 GraphQL API）
# ---------------------------------------------------------------------------

@register
class EpicGamesFreeCollector(BaseCollector):
    name = "epic_games_free"
    API_URL = (
        "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    )

    def collect(self) -> list[dict[str, Any]]:
        try:
            resp = requests.get(
                self.API_URL,
                timeout=self.REQUEST_TIMEOUT,
                params={"locale": "ja", "country": "JP", "allowCountries": "JP"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("EpicGames API error: %s", exc)
            return []

        elements = (
            data.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        )
        items: list[dict[str, Any]] = []

        for elem in elements:
            promotions = elem.get("promotions") or {}
            offer_groups = promotions.get("promotionalOffers") or []

            for group in offer_groups:
                for offer in group.get("promotionalOffers", []):
                    disc = offer.get("discountSetting", {})
                    if disc.get("discountPercentage") != 0:
                        continue  # 無料ではない

                    title: str = elem.get("title", "").strip()
                    slug: str = (
                        elem.get("productSlug")
                        or elem.get("urlSlug")
                        or ""
                    ).strip()
                    if not title or not slug:
                        continue

                    url = f"https://store.epicgames.com/ja/p/{slug}"
                    description: str = (elem.get("description") or "")[:120]
                    original_price: str = (
                        elem.get("price", {})
                        .get("totalPrice", {})
                        .get("fmtPrice", {})
                        .get("originalPrice", "")
                    )

                    items.append(
                        {
                            "title": title,
                            "url": url,
                            "source": self.name,
                            "summary": description,
                            "value": original_price if original_price else "無料",
                            "expires_at": offer.get("endDate"),
                            "category": "game",
                        }
                    )

        logger.info("EpicGames: %d items collected", len(items))
        return items


# ---------------------------------------------------------------------------
# モックデータ — dry-run・テスト用
# ---------------------------------------------------------------------------

@register
class MockCollector(BaseCollector):
    """dry-run・テスト用のサンプルデータを返す。実際の API は呼ばない。"""
    name = "mock"

    def collect(self) -> list[dict[str, Any]]:
        return [
            {
                "title": "Epic Gamesサンプルゲーム",
                "url": "https://store.epicgames.com/ja/p/sample-game",
                "source": self.name,
                "summary": "アクションRPGが期間限定で完全無料配布中です。",
                "value": "¥2,640相当",
                "expires_at": "2026-04-10T15:00:00Z",
                "category": "game",
            },
            {
                "title": "クリエイティブツール Pro",
                "url": "https://example-official.com/tool-pro-free",
                "source": self.name,
                "summary": "プロ向けデザインツールが3ヶ月間無料で使えるキャンペーン。",
                "value": "¥15,000相当",
                "expires_at": "2026-03-31T23:59:00Z",
                "category": "software",
            },
            {
                "title": "Adobeセール対象ソフト",
                "url": "https://example-official.com/sale",
                "source": self.name,
                "summary": "定番ソフトウェアが最大50%OFF。",
                "value": "50%OFF",
                "expires_at": "2026-04-05T23:59:00Z",
                "category": "software",
            },
            {
                "title": "期限切れサンプル（除外されるべき）",
                "url": "https://example-official.com/expired",
                "source": self.name,
                "summary": "このアイテムは期限切れのテスト用データです。",
                "value": "無料",
                "expires_at": "2024-01-01T00:00:00Z",
                "category": "other",
            },
            {
                "title": "URL なしサンプル（除外されるべき）",
                "url": "",
                "source": self.name,
                "summary": "公式URLがないので除外されるべきサンプルです。",
                "value": "無料",
                "expires_at": "2026-05-01T00:00:00Z",
                "category": "other",
            },
        ]


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def collect_all(
    sources: list[str] | None = None,
    use_mock: bool = False,
) -> list[dict[str, Any]]:
    """
    登録済みコレクターからすべて収集して返す。

    Args:
        sources: 指定した場合、そのソース名のみ収集する。
        use_mock: True の場合 MockCollector のみ使用する。
    """
    results: list[dict[str, Any]] = []

    for cls in _REGISTRY:
        collector = cls()
        if use_mock and collector.name != "mock":
            continue
        if not use_mock and collector.name == "mock":
            continue
        if sources and collector.name not in sources:
            continue

        logger.info("Collecting from '%s'...", collector.name)
        try:
            items = collector.collect()
        except Exception as exc:
            logger.error("Collector '%s' raised: %s", collector.name, exc)
            items = []

        logger.info("  -> %d raw items", len(items))
        results.extend(items)

    return results
