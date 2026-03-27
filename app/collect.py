"""
collect.py — 公式ソースからお得情報を収集する。

各 Collector は collect() メソッドを実装し、生のdictリストを返す。
@register デコレーターで自動登録される。
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

_REGISTRY: list[type["BaseCollector"]] = []


def register(cls: type["BaseCollector"]) -> type["BaseCollector"]:
    """コレクターをグローバルレジストリに登録するデコレーター。"""
    _REGISTRY.append(cls)
    return cls


class BaseCollector:
    name: str = "base"
    REQUEST_TIMEOUT: int = 15

    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError


def _clean_slug(raw: str | None) -> str:
    """Epic の slug 候補をURL用に整形する。"""
    slug = (raw or "").strip().strip("/")
    if not slug:
        return ""

    # /home が付くことがあるので落とす
    if slug.endswith("/home"):
        slug = slug[:-5].rstrip("/")

    return slug


def _looks_like_opaque_id(slug: str) -> bool:
    """
    39e8285c0... のようなIDっぽい値を弾く。
    ハイフン無しの長い16進文字列は商品ページslugとしては怪しい。
    """
    return bool(re.fullmatch(r"[0-9a-f]{16,}", slug.lower()))


def _pick_epic_url(elem: dict[str, Any], title: str) -> str:
    """
    Epic の正式ページURLをなるべく壊れにくく組み立てる。
    優先順:
    1. catalogNs.mappings[].pageSlug
    2. offerMappings[].pageSlug
    3. productSlug
    4. urlSlug
    5. 最後の保険として公式検索URL
    """
    candidates: list[str] = []

    catalog_ns = elem.get("catalogNs") or {}
    for mapping in catalog_ns.get("mappings") or []:
        page_slug = _clean_slug(mapping.get("pageSlug"))
        if page_slug:
            candidates.append(page_slug)

    for mapping in elem.get("offerMappings") or []:
        page_slug = _clean_slug(mapping.get("pageSlug"))
        if page_slug:
            candidates.append(page_slug)

    for raw in (elem.get("productSlug"), elem.get("urlSlug")):
        slug = _clean_slug(raw)
        if slug:
            candidates.append(slug)

    for slug in candidates:
        if _looks_like_opaque_id(slug):
            continue
        return f"https://store.epicgames.com/ja/p/{slug}"

    # slug が壊れている/取れない場合の保険
    return (
        "https://store.epicgames.com/ja/browse"
        f"?q={quote_plus(title)}&sortBy=relevancy&sortDir=DESC&count=40"
    )


# ---------------------------------------------------------------------------
# Epic Games — 無料ゲーム（公式 GraphQL API）
# ---------------------------------------------------------------------------

@register
class EpicGamesFreeCollector(BaseCollector):
    name = "epic_games_free"
    API_URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"

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

                    title: str = (elem.get("title") or "").strip()
                    if not title:
                        continue

                    url = _pick_epic_url(elem, title)
                    if not url:
                        continue

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
