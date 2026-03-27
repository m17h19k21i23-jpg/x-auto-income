"""app/score.py のテスト。"""
from __future__ import annotations

import pytest
from tests.conftest import make_item
from app.score import score_item, score_and_filter


class TestScoreItem:
    def test_free_game_gets_high_score(self):
        item = make_item(value="¥2,640相当", category="game", expires_at="2099-01-01T00:00:00Z")
        scored = score_item(item)
        assert scored["score"] > 0.5

    def test_free_value_bonus(self):
        item_free = make_item(value="無料", category="other", expires_at=None)
        item_empty = make_item(value="", category="other", expires_at=None)
        scored_free = score_item(item_free)
        scored_empty = score_item(item_empty)
        assert scored_free["score"] > scored_empty["score"]

    def test_with_deadline_beats_without(self):
        item_with = make_item(value="無料", expires_at="2099-01-01T00:00:00Z")
        item_without = make_item(value="無料", expires_at=None)
        score_item(item_with)
        score_item(item_without)
        assert item_with["score"] > item_without["score"]

    def test_score_capped_at_one(self):
        item = make_item(
            value="¥100,000相当",
            category="game",
            expires_at="2099-01-01T00:00:00Z",
            summary="A" * 50,
        )
        scored = score_item(item)
        assert scored["score"] <= 1.0

    def test_score_non_negative(self):
        item = make_item(value="", category="other", expires_at=None, summary="")
        scored = score_item(item)
        assert scored["score"] >= 0.0

    def test_large_yen_beats_small_yen(self):
        item_large = make_item(value="¥10,000相当", expires_at="2099-01-01T00:00:00Z")
        item_small = make_item(value="¥100相当", expires_at="2099-01-01T00:00:00Z")
        score_item(item_large)
        score_item(item_small)
        assert item_large["score"] > item_small["score"]


class TestScoreAndFilter:
    def test_low_score_items_removed(self):
        items = [
            make_item(id="a", value="", category="other", expires_at=None, summary=""),
            make_item(id="b", value="¥5,000相当", category="game", expires_at="2099-01-01T00:00:00Z", summary="A" * 40),
        ]
        passing, dropped = score_and_filter(items, min_score=0.5)
        assert dropped >= 1
        # item b は高スコアなので通る
        assert any(i["id"] == "b" for i in passing)

    def test_sorted_by_score_desc(self):
        items = [
            make_item(id="low", value="", category="other", expires_at="2099-01-01T00:00:00Z"),
            make_item(id="high", value="無料", category="game", expires_at="2099-01-01T00:00:00Z", summary="A" * 40),
        ]
        passing, _ = score_and_filter(items, min_score=0.0)
        if len(passing) >= 2:
            assert passing[0]["score"] >= passing[1]["score"]
