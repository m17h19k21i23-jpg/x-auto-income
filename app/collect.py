"""
collect.py — AI / SaaS / 自動化ツール deals 情報を収集する。

各 Collector は collect() メソッドを実装し、生のdictリストを返す。
@register デコレーターで自動登録される。

登録済みコレクター（デフォルト実行対象）:
  - AppSumoCollector: AppSumo の deals 一覧（公開ページ）
  - MockCollector: dry-run・テスト用サンプルデータ

サブ用途（sources 明示指定時のみ）:
  - EpicGamesFreeCollector: Epic Games Store の無料配布
"""
from __future__ import annotations

import json
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
# AppSumo — AI / SaaS deals（公開ページ __NEXT_DATA__ 経由）
# ---------------------------------------------------------------------------

@register
class AppSumoCollector(BaseCollector):
    """
    AppSumo の deals 一覧を公開ページから取得する。

    公開ページ: https://appsumo.com/browse/
    Next.js の __NEXT_DATA__ に埋め込まれた JSON を解析する。
    取得できない場合は graceful に 0 件を返す。
    """

    name = "appsumo"
    BROWSE_URL = "https://appsumo.com/browse/"

    _CATEGORY_MAP: dict[str, str] = {
        "ai": "ai_tool",
        "automation": "ai_tool",
        "generativeai": "ai_tool",
        "generative": "ai_tool",
        "productivity": "saas",
        "marketing": "saas",
        "design": "saas",
        "development": "saas",
        "business": "saas",
        "sales": "saas",
        "seo": "saas",
        "analytics": "saas",
        "writing": "saas",
        "content": "saas",
        "education": "saas",
        "finance": "saas",
        "customer": "saas",
    }

    # キーワード → 日本語用途ラベル（先にマッチしたものを採用）
    _USE_CASE_KEYWORDS: list[tuple[list[str], str]] = [
        (["seo", "keyword research", "backlink", "search rank"], "SEO分析"),
        (["transcri", "speech to text", "voice to text", "audio to text"], "音声文字起こし"),
        (["video edit", "youtube", "reel", "clip", "subtitle", "caption"], "動画制作支援"),
        (["social media", "instagram", "linkedin", "facebook", "tweet", "post schedule", "sns"], "SNS投稿支援"),
        (["cold email", "email outreach", "newsletter", "email automat"], "メール自動化"),
        (["sales", "crm", "lead gen", "pipeline", "prospect"], "営業・CRM支援"),
        (["customer support", "helpdesk", "chatbot", "live chat", "ticketing"], "カスタマーサポート"),
        (["no-code", "nocode", "workflow automat", "zapier", "integration automat"], "ノーコード自動化"),
        (["project management", "task management", "team collaborat", "gantt"], "タスク・プロジェクト管理"),
        (["analytic", "dashboard", "reporting", "data insight", "bi tool"], "データ分析"),
        (["recruit", "hiring", "hr tool", "talent acqui", "applicant"], "HR・採用支援"),
        (["invoice", "billing", "bookkeep", "financ", "accounting"], "請求・財務管理"),
        (["developer", "devops", "api tool", "github", "code review", "deploy"], "開発者ツール"),
        (["education", "e-learning", "course", "lms", "online learning"], "学習・教育支援"),
        (["marketing automat", "campaign", "advertis"], "マーケティング"),
        (["image gen", "graphic design", "banner", "visual", "photo edit", "ai image"], "AI画像・デザイン"),
        (["writing", "content creat", "copywriting", "blog", "article gen"], "AI文章生成"),
        (["productivity", "time track", "focus", "calendar", "schedule"], "生産性向上"),
        (["chat", "llm", "gpt", "openai", "claude", "ai assistant"], "AI活用ツール"),
        (["automat", "workflow"], "業務自動化"),
    ]

    _CATEGORY_USE_CASE_FALLBACK: dict[str, str] = {
        "ai_tool": "AI活用ツール",
        "saas": "SaaSツール",
        "game": "ゲーム",
        "other": "その他ツール",
    }

    # 用途ラベル → 対象ユーザー
    _TARGET_USER_MAP: dict[str, str] = {
        "SEO分析": "SEO担当・ブロガー向け",
        "音声文字起こし": "ライター・動画制作者向け",
        "動画制作支援": "動画クリエイター向け",
        "SNS投稿支援": "SNS担当・マーケター向け",
        "メール自動化": "営業・マーケター向け",
        "営業・CRM支援": "営業チーム向け",
        "カスタマーサポート": "EC / サポート担当向け",
        "ノーコード自動化": "非エンジニア・業務担当向け",
        "タスク・プロジェクト管理": "チームリーダー向け",
        "データ分析": "マーケター・経営者向け",
        "HR・採用支援": "人事・採用担当向け",
        "請求・財務管理": "経営者・経理担当向け",
        "開発者ツール": "エンジニア向け",
        "学習・教育支援": "教育担当・学習者向け",
        "マーケティング": "マーケター向け",
        "AI画像・デザイン": "デザイナー・制作会社向け",
        "AI文章生成": "コンテンツ担当・ライター向け",
        "生産性向上": "ビジネスパーソン向け",
        "AI活用ツール": "AI活用したいビジネス担当向け",
        "業務自動化": "バックオフィス・業務担当向け",
        "SaaSツール": "ビジネス担当向け",
        "その他ツール": "一般ユーザー向け",
        "ゲーム": "ゲーマー向け",
    }

    # __NEXT_DATA__ から商品リストを取り出すパス候補
    # 要素に int が含まれる場合はリストのインデックスとして扱う
    _PRODUCT_PATHS: list[list[str | int]] = [
        ["props", "pageProps", "fallbackData", 0, "deals"],   # 現行構造（2026-03）
        ["props", "pageProps", "products"],
        ["props", "pageProps", "deals"],
        ["props", "pageProps", "items"],
        ["props", "pageProps", "initialData", "products"],
        ["props", "pageProps", "initialData", "deals"],
    ]

    def collect(self) -> list[dict[str, Any]]:
        try:
            resp = requests.get(
                self.BROWSE_URL,
                timeout=self.REQUEST_TIMEOUT,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "ja,en;q=0.9",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("AppSumo fetch error: %s", exc)
            return []

        raw_data = self._extract_next_data(resp.text)
        if raw_data is None:
            logger.warning("AppSumo: __NEXT_DATA__ not found — returning 0 items")
            return []

        products = self._find_products(raw_data)
        if not products:
            logger.warning("AppSumo: no products found in page data — returning 0 items")
            return []

        items: list[dict[str, Any]] = []
        for deal in products:
            item = self._parse_deal(deal)
            if item:
                items.append(item)

        logger.info("AppSumo: %d items collected", len(items))
        return items

    def _extract_next_data(self, html: str) -> dict[str, Any] | None:
        """HTML から <script id="__NEXT_DATA__"> を抽出してパースする。"""
        m = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception as exc:
            logger.error("AppSumo: failed to parse __NEXT_DATA__: %s", exc)
            return None

    def _find_products(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """__NEXT_DATA__ 内の商品リストを複数パスから探す。
        パスに int が含まれる場合はリストのインデックスとして扱う。
        """
        for path in self._PRODUCT_PATHS:
            node: Any = data
            for key in path:
                if isinstance(key, int):
                    if not isinstance(node, list) or key >= len(node):
                        node = None
                        break
                    node = node[key]
                else:
                    if not isinstance(node, dict):
                        node = None
                        break
                    node = node.get(key)
            if isinstance(node, list) and node:
                logger.debug("AppSumo: found products at path %s", path)
                return node
        return []

    def _parse_deal(self, deal: dict[str, Any]) -> dict[str, Any] | None:
        """1 件の deal dict を内部形式に変換する。取得できなければ None を返す。"""
        # 終了済みの deal は除外
        if deal.get("has_ended"):
            return None

        # タイトル: public_name（現行）→ name → title の順で取得
        title: str = (
            deal.get("public_name") or deal.get("name") or deal.get("title") or ""
        ).strip()
        if not title:
            return None

        # URL: get_absolute_url（現行・相対パス）→ public_url → url → slug の順
        raw_url: str = (
            deal.get("get_absolute_url")
            or deal.get("public_url")
            or deal.get("url")
            or ""
        ).strip()
        if raw_url.startswith("/"):
            public_url = f"https://appsumo.com{raw_url}"
        elif raw_url.startswith("http"):
            public_url = raw_url
        else:
            slug = (deal.get("slug") or deal.get("product_slug") or "").strip()
            public_url = f"https://appsumo.com/products/{slug}" if slug else ""
        if not public_url:
            return None

        # 説明文: card_description（現行）→ short_description → description の順
        description: str = (
            deal.get("card_description")
            or deal.get("short_description")
            or deal.get("description")
            or ""
        ).strip()

        # 価格: current_price → price（現行）の順
        current_price = deal.get("current_price") if deal.get("current_price") is not None else deal.get("price")
        original_price = deal.get("original_price") or deal.get("retail_price")

        # Lifetime Deal 判定: unique_plan_types に "Lifetime Deal" が含まれるか
        plan_types: list[list[Any]] = deal.get("unique_plan_types") or []
        is_ltd_plan = any(
            isinstance(pt, (list, tuple)) and pt and "lifetime" in str(pt[0]).lower()
            for pt in plan_types
        )

        value, summary = self._format_value(
            title, description, current_price, original_price, is_ltd_plan=is_ltd_plan
        )

        # カテゴリ: attributes.categories（現行）→ taxonomy → categories フィールド
        attrs = deal.get("attributes") or {}
        raw_cats: list[str] = (
            attrs.get("categories")
            or attrs.get("category")
            or deal.get("categories")
            or []
        )
        if not raw_cats:
            taxonomy = deal.get("taxonomy") or {}
            cat_node = taxonomy.get("category") or {}
            cat_val = cat_node.get("value_enumeration") or ""
            raw_cats = [cat_val] if cat_val else []

        category = self._map_category(raw_cats)

        # 期限: dates.end_date（現行）→ end_date → expires_at の順
        dates_node = deal.get("dates") or {}
        expires_at: str | None = (
            dates_node.get("end_date")
            or deal.get("end_date")
            or deal.get("expires_at")
        )

        use_case = self._map_use_case(title, description, category)
        target_user = self._TARGET_USER_MAP.get(use_case, "ビジネス担当向け")

        # original_value: 元値の表示用（UI でのstrikethrough 表示向け）
        original_value = ""
        if original_price is not None:
            try:
                orig_f = float(str(original_price).replace(",", ""))
                if orig_f > 0:
                    original_value = f"${int(orig_f)}/年" if is_ltd_plan and orig_f > 100 else f"${int(orig_f)}"
            except (ValueError, TypeError):
                pass

        return {
            "title": title,
            "url": public_url,
            "source": self.name,
            "summary": summary,
            "value": value,
            "original_value": original_value,
            "use_case": use_case,
            "target_user": target_user,
            "expires_at": expires_at,
            "category": category,
        }

    def _format_value(
        self,
        title: str,
        description: str,
        current_price: Any,
        original_price: Any,
        is_ltd_plan: bool = False,
    ) -> tuple[str, str]:
        """価格情報から value 文字列と日本語 summary を生成する。英語説明文は含めない。"""
        combined = (title + " " + description).lower()
        is_ltd = is_ltd_plan or "lifetime" in combined or "ltd" in combined or "買い切り" in combined
        is_trial = "free trial" in combined or "trial" in combined

        if current_price is not None:
            try:
                cur = float(str(current_price).replace(",", ""))
            except ValueError:
                cur = None
        else:
            cur = None

        if original_price is not None:
            try:
                orig = float(str(original_price).replace(",", ""))
            except ValueError:
                orig = None
        else:
            orig = None

        if cur == 0.0:
            value = "無料トライアル" if is_trial else "無料"
            summary = "無料トライアルで試せます。" if is_trial else "今すぐ無料で使えます。"
        elif is_ltd and cur is not None:
            value = f"LTD ${int(cur)}"
            if orig:
                summary = f"通常${int(orig)}/年のSaaSが買い切り${int(cur)}で使い放題。"
            else:
                summary = f"買い切り${int(cur)}でずっと使えるライフタイムディール。"
        elif cur is not None and orig is not None and orig > cur:
            pct = int((1 - cur / orig) * 100)
            value = f"${int(cur)}（{pct}%OFF）"
            summary = f"通常${int(orig)}が${int(cur)}に値下げ中（{pct}%OFF）。"
        elif cur is not None:
            value = f"${int(cur)}"
            summary = f"AppSumoで${int(cur)}から入手可能。"
        else:
            value = "要確認"
            summary = "詳細はAppSumoの公式ページをご確認ください。"

        return value, summary

    def _map_use_case(self, title: str, description: str, category: str) -> str:
        """タイトル・説明・カテゴリから日本語用途ラベルを決定する。"""
        combined = (title + " " + description).lower()
        for keywords, label in self._USE_CASE_KEYWORDS:
            if any(kw in combined for kw in keywords):
                return label
        return self._CATEGORY_USE_CASE_FALLBACK.get(category, "SaaSツール")

    def _map_category(self, raw_cats: list[str]) -> str:
        """AppSumo カテゴリ名を内部カテゴリに変換する。"""
        for cat in raw_cats:
            normalized = cat.lower().replace("-", "").replace("_", "")
            for key, internal in self._CATEGORY_MAP.items():
                if key in normalized:
                    return internal
        return "saas"


# ---------------------------------------------------------------------------
# Epic Games — 無料ゲーム（公式 GraphQL API）※サブ用途として維持
# @register を外しているため collect_all() のデフォルト実行対象外。
# sources=["epic_games_free"] と明示した場合のみ使用する。
# ---------------------------------------------------------------------------

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

                    original_price: str = (
                        elem.get("price", {})
                        .get("totalPrice", {})
                        .get("fmtPrice", {})
                        .get("originalPrice", "")
                    )

                    if original_price:
                        summary = f"通常{original_price}が期間限定で無料配布中です。"
                    else:
                        summary = "Epic Games Storeで期間限定無料配布中！"

                    items.append(
                        {
                            "title": title,
                            "url": url,
                            "source": self.name,
                            "summary": summary,
                            "value": "無料",
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
                "title": "TaskFlow AI",
                "url": "https://appsumo.com/products/taskflow-ai",
                "source": self.name,
                "summary": "AIがタスクの優先順位を自動判断し、チーム全体の作業進捗を一元管理。",
                "value": "LTD $49",
                "original_value": "$199/年",
                "use_case": "タスク・プロジェクト管理",
                "target_user": "チームリーダー向け",
                "expires_at": "2026-04-10T15:00:00Z",
                "category": "ai_tool",
            },
            {
                "title": "ContentGenius Pro",
                "url": "https://appsumo.com/products/contentgenius-pro",
                "source": self.name,
                "summary": "AIが記事・広告コピーを自動生成し、SEOスコアもリアルタイムで最適化。",
                "value": "$79（87%OFF）",
                "original_value": "$588",
                "use_case": "AI文章生成",
                "target_user": "コンテンツ担当・ライター向け",
                "expires_at": "2026-04-17T15:00:00Z",
                "category": "ai_tool",
            },
            {
                "title": "AutomateHub",
                "url": "https://appsumo.com/products/automatehub",
                "source": self.name,
                "summary": "コードなしで業務フローを組み立て、繰り返し作業を丸ごと自動化。",
                "value": "無料トライアル",
                "original_value": "",
                "use_case": "ノーコード自動化",
                "target_user": "非エンジニア・業務担当向け",
                "expires_at": "2026-04-05T23:59:00Z",
                "category": "saas",
            },
            {
                "title": "期限切れサンプル（除外されるべき）",
                "url": "https://appsumo.com/products/expired-sample",
                "source": self.name,
                "summary": "このアイテムは期限切れのテスト用データです。",
                "value": "LTD $29",
                "original_value": "",
                "use_case": "SaaSツール",
                "target_user": "ビジネス担当向け",
                "expires_at": "2024-01-01T00:00:00Z",
                "category": "saas",
            },
            {
                "title": "URL なしサンプル（除外されるべき）",
                "url": "",
                "source": self.name,
                "summary": "公式URLがないので除外されるべきサンプルです。",
                "value": "LTD $19",
                "original_value": "",
                "use_case": "SaaSツール",
                "target_user": "ビジネス担当向け",
                "expires_at": "2026-05-01T00:00:00Z",
                "category": "saas",
            },
        ]


# ---------------------------------------------------------------------------
# オプショナルコレクター（@register 対象外・明示指定時のみ使用）
# ---------------------------------------------------------------------------

# Epic は sources=["epic_games_free"] と明示した場合のみ実行される
_EXTRAS: list[type["BaseCollector"]] = [EpicGamesFreeCollector]

# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

# sources を指定しない場合のデフォルト実行対象（Epic を含まない）
DEFAULT_SOURCES: frozenset[str] = frozenset({"appsumo"})


def collect_all(
    sources: list[str] | None = None,
    use_mock: bool = False,
) -> list[dict[str, Any]]:
    """
    コレクターからデータを収集して返す。

    Args:
        sources: 指定した場合、そのソース名のみ収集する。
                 None の場合は DEFAULT_SOURCES（appsumo）のみ実行する。
                 epic_games_free を含めるには明示指定が必要。
        use_mock: True の場合 MockCollector のみ使用する。
    """
    results: list[dict[str, Any]] = []

    # 実行対象ソース集合を確定する
    if use_mock:
        active_sources: frozenset[str] | None = None  # mock のみの特別ルート
    elif sources:
        active_sources = frozenset(sources)
    else:
        active_sources = DEFAULT_SOURCES

    # _REGISTRY（自動登録）+ _EXTRAS（オプショナル）を合わせて走査
    all_classes = list(_REGISTRY) + _EXTRAS

    for cls in all_classes:
        collector = cls()

        if use_mock:
            if collector.name != "mock":
                continue
        else:
            if collector.name == "mock":
                continue
            if active_sources is not None and collector.name not in active_sources:
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
