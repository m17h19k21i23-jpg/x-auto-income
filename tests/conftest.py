"""共有フィクスチャ。"""
from __future__ import annotations

import pytest
from app.normalize import Item


def make_item(**kwargs) -> Item:
    """テスト用の Item を生成するヘルパー。"""
    defaults: Item = {
        "id": "test001",
        "title": "TaskFlow AI",
        "url": "https://appsumo.com/products/taskflow-ai",
        "source": "appsumo",
        "summary": "AIがタスクの優先順位を自動判断し、チーム全体の作業進捗を一元管理。",
        "value": "LTD $49",
        "original_value": "$199/年",
        "use_case": "タスク・プロジェクト管理",
        "target_user": "チームリーダー向け",
        "category": "ai_tool",
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
        make_item(id="item001", title="ContentGenius Pro", value="$79（87%OFF）", score=0.8),
        make_item(id="item002", title="AutomateHub", value="無料トライアル", score=0.6),
        make_item(id="item003", title="DataSift AI", value="LTD $99", score=0.75),
    ]
