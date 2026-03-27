"""app/normalize.py のテスト。"""
from __future__ import annotations

import pytest
from app.normalize import normalize, normalize_all


class TestNormalize:
    def test_valid_item(self):
        raw = {
            "title": "テストゲーム",
            "url": "https://store.epicgames.com/ja/p/test",
            "source": "mock",
            "summary": "テスト用サンプルです。",
            "value": "無料",
            "expires_at": "2099-12-31T23:59:00Z",
            "category": "game",
        }
        item = normalize(raw)
        assert item is not None
        assert item["title"] == "テストゲーム"
        assert item["url"] == "https://store.epicgames.com/ja/p/test"
        assert item["score"] == 0.0  # スコアは normalize 時点で 0.0
        assert item["posted_at"] is None
        assert len(item["id"]) == 16  # SHA-256 先頭 16 文字

    def test_empty_title_dropped(self):
        raw = {
            "title": "",
            "url": "https://example.com",
            "source": "mock",
        }
        assert normalize(raw) is None

    def test_empty_url_dropped(self):
        raw = {
            "title": "テスト",
            "url": "",
            "source": "mock",
        }
        assert normalize(raw) is None

    def test_invalid_url_dropped(self):
        raw = {
            "title": "テスト",
            "url": "not-a-url",
            "source": "mock",
        }
        assert normalize(raw) is None

    def test_expired_dropped(self):
        raw = {
            "title": "テスト",
            "url": "https://example.com",
            "source": "mock",
            "expires_at": "2020-01-01T00:00:00Z",  # 過去
        }
        assert normalize(raw) is None

    def test_no_expiry_kept(self):
        """expires_at がない場合は期限なし扱いで残す。"""
        raw = {
            "title": "テスト",
            "url": "https://example.com",
            "source": "mock",
            "expires_at": None,
        }
        item = normalize(raw)
        assert item is not None
        assert item["expires_at"] is None

    def test_same_url_same_id(self):
        raw1 = {"title": "A", "url": "https://example.com/a", "source": "mock"}
        raw2 = {"title": "B", "url": "https://example.com/a", "source": "mock"}
        item1 = normalize(raw1)
        item2 = normalize(raw2)
        assert item1 is not None and item2 is not None
        assert item1["id"] == item2["id"]

    def test_different_url_different_id(self):
        raw1 = {"title": "A", "url": "https://example.com/a", "source": "mock"}
        raw2 = {"title": "B", "url": "https://example.com/b", "source": "mock"}
        item1 = normalize(raw1)
        item2 = normalize(raw2)
        assert item1 is not None and item2 is not None
        assert item1["id"] != item2["id"]


class TestNormalizeAll:
    def test_mixed_valid_invalid(self):
        raws = [
            {"title": "A", "url": "https://example.com/a", "source": "mock"},
            {"title": "", "url": "https://example.com/b", "source": "mock"},  # 除外
            {"title": "C", "url": "", "source": "mock"},  # 除外
            {
                "title": "D",
                "url": "https://example.com/d",
                "source": "mock",
                "expires_at": "2020-01-01T00:00:00Z",  # 期限切れ・除外
            },
        ]
        items, stats = normalize_all(raws)
        assert len(items) == 1
        assert stats["total"] == 4
        assert stats["valid"] == 1
        assert stats["dropped"] == 3
