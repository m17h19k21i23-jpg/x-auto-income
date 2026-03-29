"""app/collect.py の AppSumoCollector テスト。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.collect import AppSumoCollector


# ---------------------------------------------------------------------------
# ヘルパー: テスト用 __NEXT_DATA__ HTML を生成する
# ---------------------------------------------------------------------------

def _make_html(deals: list[dict]) -> str:
    """fallbackData[0].deals に指定のdealsを含む Next.js HTML を生成する。"""
    next_data = {
        "props": {
            "pageProps": {
                "fallbackData": [
                    {
                        "deals": deals,
                        "alternative_skus": [],
                        "meta": {"total_results": len(deals), "total_pages": 1, "page": 1, "per_page": 20},
                    }
                ],
                "isCollectionBrowsePage": True,
            },
            "__N_SSG": True,
        },
        "page": "/browse/[[...slug]]",
        "query": {},
        "buildId": "test-build",
    }
    payload = json.dumps(next_data, ensure_ascii=False)
    return f'<html><head><script id="__NEXT_DATA__" type="application/json">{payload}</script></head><body></body></html>'


def _make_deal(**kwargs) -> dict:
    """テスト用の deal dict を生成する。デフォルト値込み。"""
    defaults = {
        "id": 1,
        "public_name": "TestTool AI",
        "card_description": "An AI-powered tool for productivity",
        "get_absolute_url": "/products/testtool-ai/",
        "slug": "testtool-ai",
        "has_ended": False,
        "price": 49,
        "original_price": 588,
        "unique_plan_types": [["Lifetime Deal", None, None]],
        "dates": {"start_date": "2026-01-01T00:00:00Z", "end_date": None},
        "taxonomy": {
            "category": {"value_enumeration": "productivity", "search_values": ["Productivity"]},
        },
        "attributes": {
            "categories": ["Generative AI", "Task management"],
        },
    }
    defaults.update(kwargs)
    return defaults


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------

class TestAppSumoCollectorFindProducts:
    def test_finds_deals_in_fallback_data(self):
        """fallbackData[0].deals パスから商品リストを取得できる。"""
        collector = AppSumoCollector()
        deal = _make_deal()
        data = {
            "props": {
                "pageProps": {
                    "fallbackData": [{"deals": [deal], "meta": {}}],
                }
            }
        }
        products = collector._find_products(data)
        assert len(products) == 1
        assert products[0]["public_name"] == "TestTool AI"

    def test_falls_back_to_legacy_paths(self):
        """legacy パス（pageProps.products）でも取得できる。"""
        collector = AppSumoCollector()
        deal = _make_deal()
        data = {"props": {"pageProps": {"products": [deal]}}}
        products = collector._find_products(data)
        assert len(products) == 1

    def test_returns_empty_for_unknown_structure(self):
        """既知パスに何もない場合は空リストを返す。"""
        collector = AppSumoCollector()
        products = collector._find_products({"props": {"pageProps": {}}})
        assert products == []


class TestAppSumoCollectorParseDeal:
    def test_parses_basic_fields(self):
        """基本フィールドを正しくパースできる。"""
        collector = AppSumoCollector()
        deal = _make_deal()
        item = collector._parse_deal(deal)
        assert item is not None
        assert item["title"] == "TestTool AI"
        assert item["url"] == "https://appsumo.com/products/testtool-ai/"
        assert item["source"] == "appsumo"
        assert "AI" in item["summary"] or "productivity" in item["summary"].lower() or item["summary"]

    def test_relative_url_becomes_absolute(self):
        """get_absolute_url の相対パスを絶対 URL に変換する。"""
        collector = AppSumoCollector()
        deal = _make_deal(get_absolute_url="/products/my-tool/")
        item = collector._parse_deal(deal)
        assert item is not None
        assert item["url"] == "https://appsumo.com/products/my-tool/"

    def test_has_ended_deal_is_excluded(self):
        """has_ended=True の deal は除外される。"""
        collector = AppSumoCollector()
        deal = _make_deal(has_ended=True)
        item = collector._parse_deal(deal)
        assert item is None

    def test_missing_title_returns_none(self):
        """public_name / name / title がすべて空の場合は None。"""
        collector = AppSumoCollector()
        deal = _make_deal(public_name="", slug="no-name")
        item = collector._parse_deal(deal)
        assert item is None

    def test_lifetime_deal_plan_type(self):
        """unique_plan_types に Lifetime Deal があれば LTD として value を生成する。"""
        collector = AppSumoCollector()
        deal = _make_deal(unique_plan_types=[["Lifetime Deal", None, None]], price=79)
        item = collector._parse_deal(deal)
        assert item is not None
        assert "LTD" in item["value"]
        assert "79" in item["value"]

    def test_price_discount_calculation(self):
        """original_price > current_price のとき割引率を計算する。"""
        collector = AppSumoCollector()
        deal = _make_deal(unique_plan_types=[], price=50, original_price=200)
        item = collector._parse_deal(deal)
        assert item is not None
        assert "75%OFF" in item["value"]

    def test_end_date_from_dates_field(self):
        """dates.end_date が expires_at として使われる。"""
        collector = AppSumoCollector()
        deal = _make_deal(dates={"start_date": "2026-01-01T00:00:00Z", "end_date": "2026-06-01T00:00:00Z"})
        item = collector._parse_deal(deal)
        assert item is not None
        assert item["expires_at"] == "2026-06-01T00:00:00Z"

    def test_no_url_returns_none(self):
        """URL が取得できない場合は None。"""
        collector = AppSumoCollector()
        deal = _make_deal(get_absolute_url="", public_url="", url="", slug="")
        item = collector._parse_deal(deal)
        assert item is None

    def test_ai_category_mapping(self):
        """Generative AI カテゴリが ai_tool にマップされる。"""
        collector = AppSumoCollector()
        deal = _make_deal(attributes={"categories": ["Generative AI"]})
        item = collector._parse_deal(deal)
        assert item is not None
        assert item["category"] == "ai_tool"


class TestAppSumoCollectorCollect:
    def test_collect_returns_items_from_html(self):
        """実ページ相当の HTML から複数件取得できる。"""
        collector = AppSumoCollector()
        deals = [_make_deal(id=i, public_name=f"Tool {i}", slug=f"tool-{i}") for i in range(3)]
        html = _make_html(deals)

        with patch("requests.get", return_value=_mock_response(html)):
            items = collector.collect()

        assert len(items) == 3
        assert items[0]["title"] == "Tool 0"

    def test_collect_returns_empty_on_http_error(self):
        """HTTP エラーの場合は空リストを返す。"""
        collector = AppSumoCollector()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("requests.get", return_value=mock_resp):
            items = collector.collect()

        assert items == []

    def test_collect_returns_empty_when_no_next_data(self):
        """__NEXT_DATA__ がない場合は空リストを返す。"""
        collector = AppSumoCollector()
        html = "<html><body>no script tag here</body></html>"

        with patch("requests.get", return_value=_mock_response(html)):
            items = collector.collect()

        assert items == []

    def test_collect_excludes_ended_deals(self):
        """has_ended=True の deal が結果に含まれない。"""
        collector = AppSumoCollector()
        deals = [
            _make_deal(id=1, public_name="Active", slug="active", has_ended=False),
            _make_deal(id=2, public_name="Ended", slug="ended", has_ended=True),
        ]
        html = _make_html(deals)

        with patch("requests.get", return_value=_mock_response(html)):
            items = collector.collect()

        assert len(items) == 1
        assert items[0]["title"] == "Active"
