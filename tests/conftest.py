"""共有フィクスチャ。"""
from __future__ import annotations

import pytest
from app.normalize import Item


def make_item(**kwargs) -> Item:
    """テスト用の Item を生成するヘルパー。"""
    defaults: Item = {
        "id": "test001",
        "title": "テストゲーム",
        "url": "https://store.epicgames.com/ja/p/test-game",
        "source": "mock",
        "summary": "テスト用の無料ゲームサンプルです。",
        "value": "無料",
        "category": "game",
        "expires_at": "2099-12-31T23:59:00Z",
        "score": 0.0,
        "collected_at": "2026-03-27T00:00:00Z",
        "posted_at": None,
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    return defaults


@pytest.fixture
def sample_item() -> Item:
    return make_item()


@pytest.fixture
def sample_items() -> list[Item]:
    return [
        make_item(id="item001", title="無料ゲーム A", value="¥2,640相当", score=0.8),
        make_item(id="item002", title="セールソフト B", value="50%OFF", score=0.6),
        make_item(id="item003", title="無料ツール C", value="無料", score=0.75),
    ]
