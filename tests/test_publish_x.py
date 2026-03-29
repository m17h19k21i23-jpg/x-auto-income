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
    _pages_item_url,
    _select_template,
    _TEMPLATES,
    DEFAULT_PUBLIC_SITE_URL,
    MAX_TWEET_LENGTH,
)


class TestBuildTweet:
    def test_contains_title(self):
        item = make_item(title="テストゲーム", value="無料")
        item["expires_label"] = "あと3日"
        text = _build_tweet(item, 0)
        assert "テストゲーム" in text

    def test_contains_default_pages_url_when_not_set(self):
        """PUBLIC_SITE_URL 未設定時はデフォルト速報ページ URL が本文に含まれる。"""
        item = make_item(url="https://appsumo.com/products/test", slug="test-tool")
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PUBLIC_SITE_URL", None)
            text = _build_tweet(item, 0)
        assert DEFAULT_PUBLIC_SITE_URL.rstrip("/") in text
        assert "appsumo.com" not in text

    def test_contains_pages_url(self):
        """PUBLIC_SITE_URL 設定時は速報ページのアンカー URL が本文に含まれる。"""
        item = make_item(url="https://example.com/test", slug="taskflow-ai")
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://user.github.io/repo"}):
            text = _build_tweet(item, 0)
        assert "https://user.github.io/repo/#taskflow-ai" in text
        assert "https://example.com/test" not in text

    def test_all_templates_build(self):
        item = make_item()
        item["expires_label"] = "あと2日"
        for idx in range(len(_TEMPLATES)):
            text = _build_tweet(item, idx)
            assert len(text) > 0


class TestPagesItemUrl:
    def test_returns_default_anchor_url_when_not_set(self):
        """PUBLIC_SITE_URL 未設定時はデフォルト URL + #slug を返す。"""
        item = make_item(url="https://appsumo.com/products/x", slug="x")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PUBLIC_SITE_URL", None)
            result = _pages_item_url(item)
        assert result == DEFAULT_PUBLIC_SITE_URL.rstrip("/") + "/#x"

    def test_returns_anchor_url_when_public_site_url_set(self):
        item = make_item(slug="zipchat-ai")
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://user.github.io/repo"}):
            result = _pages_item_url(item)
        assert result == "https://user.github.io/repo/#zipchat-ai"

    def test_trailing_slash_stripped(self):
        item = make_item(slug="my-tool")
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://user.github.io/repo/"}):
            result = _pages_item_url(item)
        assert result == "https://user.github.io/repo/#my-tool"

    def test_returns_none_when_slug_empty(self):
        """slug が空の場合は None を返す。"""
        item = make_item(slug="")
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://user.github.io/repo"}):
            result = _pages_item_url(item)
        assert result is None


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

    def test_validate_no_slug(self):
        """slug が空の場合はバリデーションエラーになる（landing_url 生成不可）。"""
        item = make_item(slug="")
        publisher = XPublisher()
        errors = publisher.validate(item)
        assert any("slug" in e or "landing_url" in e for e in errors)


class TestTweetUrlPolicy:
    """X 投稿の URL ポリシーに関するテスト。"""

    def test_tweet_no_appsumo_direct_url(self):
        """X 投稿本文に appsumo.com の直リンクが入らないこと。"""
        item = make_item(
            url="https://appsumo.com/products/taskflow-ai",
            slug="taskflow-ai",
        )
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://m17h19k21i23-jpg.github.io/x-auto-income/"}):
            text = _build_tweet(item, 0)
        assert "appsumo.com" not in text

    def test_tweet_contains_github_io_url(self):
        """X 投稿本文に github.io/x-auto-income/ が入ること。"""
        item = make_item(slug="taskflow-ai")
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://m17h19k21i23-jpg.github.io/x-auto-income/"}):
            text = _build_tweet(item, 0)
        assert "github.io/x-auto-income/" in text

    def test_tweet_contains_slug_anchor(self):
        """X 投稿本文に案件の #slug アンカーが入ること。"""
        item = make_item(slug="zipchat-ai")
        item["expires_label"] = "あと3日"
        with patch.dict(os.environ, {"PUBLIC_SITE_URL": "https://m17h19k21i23-jpg.github.io/x-auto-income/"}):
            text = _build_tweet(item, 0)
        assert "#zipchat-ai" in text

    def test_tweet_uses_default_url_without_env(self):
        """PUBLIC_SITE_URL 未設定でもデフォルト速報ページが使われ、直リンクは入らない。"""
        item = make_item(
            url="https://appsumo.com/products/xyz",
            slug="xyz-tool",
        )
        item["expires_label"] = "あと5日"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PUBLIC_SITE_URL", None)
            text = _build_tweet(item, 0)
        assert "appsumo.com" not in text
        assert "github.io/x-auto-income/" in text
        assert "#xyz-tool" in text
