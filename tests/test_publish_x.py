"""app/publish_x.py のテスト。"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from tests.conftest import make_item
from app.publish_x import (
    XPublisher,
    _build_tweet,
    _count_tweet_length,
    _select_template,
    _TEMPLATES,
    MAX_TWEET_LENGTH,
)


class TestBuildTweet:
    def test_contains_title(self):
        item = make_item(title="テストゲーム", value="無料")
        item["expires_label"] = "あと3日"
        text = _build_tweet(item, 0)
        assert "テストゲーム" in text

    def test_contains_url(self):
        item = make_item(url="https://example.com/test")
        item["expires_label"] = "あと3日"
        text = _build_tweet(item, 0)
        assert "https://example.com/test" in text

    def test_all_templates_build(self):
        item = make_item()
        item["expires_label"] = "あと2日"
        for idx in range(len(_TEMPLATES)):
            text = _build_tweet(item, idx)
            assert len(text) > 0


class TestCountTweetLength:
    def test_url_counted_as_23(self):
        url = "https://very-long-url-that-would-be-more-than-23-chars.example.com/path/to/page"
        text = f"テスト {url}"
        length = _count_tweet_length(text, url)
        # "テスト " (4文字) + 23 (URL) = 27
        assert length == 4 + 23


class TestSelectTemplate:
    def test_avoids_recent_3(self):
        used = [0, 1, 2]
        for _ in range(20):
            idx = _select_template(used, total_templates=6)
            assert idx not in {0, 1, 2}

    def test_works_with_empty_used(self):
        idx = _select_template([], total_templates=6)
        assert 0 <= idx < 6

    def test_fallback_when_all_used(self):
        # 全テンプレートが used にある場合でも選べる
        used = list(range(len(_TEMPLATES)))
        idx = _select_template(used)
        assert 0 <= idx < len(_TEMPLATES)


class TestXPublisher:
    def test_post_dry_run(self):
        item = make_item()
        item["expires_label"] = "あと3日"
        publisher = XPublisher()
        result = publisher.post(item, template_idx=0, dry_run=True)
        assert result["success"] is True
        assert result["tweet_id"] == "dry_run"

    def test_post_disabled_skips(self):
        item = make_item()
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {"POST_ENABLED": "false"}):
            publisher = XPublisher()
            result = publisher.post(item, template_idx=0, dry_run=False)
        assert result["success"] is True
        assert result["tweet_id"] == "skipped"

    def test_validate_empty_url(self):
        item = make_item(url="")
        publisher = XPublisher()
        errors = publisher.validate(item)
        assert any("url" in e for e in errors)
