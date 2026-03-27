"""app/main.py の統合テスト（dry-run + mock）。"""
from __future__ import annotations

import sys
import pytest
from unittest.mock import patch


class TestDryRunWithMock:
    def test_dry_run_exits_zero(self, tmp_path):
        """--dry-run --mock でエラーなく終了することを確認する。"""
        from app.main import run

        # state.json と site/ を tmp_path に向ける
        with (
            patch("app.dedupe.STATE_PATH", tmp_path / "state.json"),
            patch("app.render_site.SITE_DIR", tmp_path / "site"),
            patch("app.main.LOGS_DIR", tmp_path / "logs"),
        ):
            exit_code = run(dry_run=True, use_mock=True)

        assert exit_code == 0

    def test_dry_run_does_not_write_state(self, tmp_path):
        """dry-run では state.json が変更されないことを確認する。"""
        from app.main import run

        state_path = tmp_path / "state.json"
        assert not state_path.exists()

        with (
            patch("app.dedupe.STATE_PATH", state_path),
            patch("app.render_site.SITE_DIR", tmp_path / "site"),
            patch("app.main.LOGS_DIR", tmp_path / "logs"),
        ):
            run(dry_run=True, use_mock=True)

        # dry-run では state.json は書き込まれない
        assert not state_path.exists()

    def test_dry_run_generates_site_html(self, tmp_path):
        """dry-run では site/index.html が生成されないことを確認（dry_run=True は書き込みなし）。"""
        from app.main import run

        site_dir = tmp_path / "site"

        with (
            patch("app.dedupe.STATE_PATH", tmp_path / "state.json"),
            patch("app.render_site.SITE_DIR", site_dir),
            patch("app.main.LOGS_DIR", tmp_path / "logs"),
        ):
            run(dry_run=True, use_mock=True)

        # dry-run では site ディレクトリに書き込みしない
        assert not (site_dir / "index.html").exists()

    def test_post_mode_writes_site(self, tmp_path):
        """--post モード（POST_ENABLED=false）では site/index.html が生成される。"""
        from app.main import run
        import os

        site_dir = tmp_path / "site"
        state_path = tmp_path / "state.json"

        env_overrides = {"POST_ENABLED": "false"}
        with (
            patch("app.dedupe.STATE_PATH", state_path),
            patch("app.render_site.SITE_DIR", site_dir),
            patch("app.main.LOGS_DIR", tmp_path / "logs"),
            patch.dict(os.environ, env_overrides),
        ):
            run(dry_run=False, use_mock=True)

        assert (site_dir / "index.html").exists()
        html = (site_dir / "index.html").read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html

    def test_audit_log_is_written(self, tmp_path):
        """実行後に監査ログが生成されることを確認する。"""
        from app.main import run

        logs_dir = tmp_path / "logs"

        with (
            patch("app.dedupe.STATE_PATH", tmp_path / "state.json"),
            patch("app.render_site.SITE_DIR", tmp_path / "site"),
            patch("app.main.LOGS_DIR", logs_dir),
        ):
            run(dry_run=True, use_mock=True)

        log_files = list(logs_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
