"""app/dedupe.py のテスト。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from tests.conftest import make_item
from app.dedupe import (
    filter_new,
    load_state,
    mark_posted,
    save_state,
    update_run_stats,
    _empty_state,
)


class TestFilterNew:
    def test_removes_known_ids(self):
        state = _empty_state()
        state["posted_ids"] = ["item001", "item002"]
        items = [
            make_item(id="item001"),
            make_item(id="item002"),
            make_item(id="item003"),
        ]
        new_items, dup_count = filter_new(items, state)
        assert len(new_items) == 1
        assert new_items[0]["id"] == "item003"
        assert dup_count == 2

    def test_empty_state_passes_all(self):
        state = _empty_state()
        items = [make_item(id="x"), make_item(id="y")]
        new_items, dup_count = filter_new(items, state)
        assert len(new_items) == 2
        assert dup_count == 0

    def test_all_duplicate(self):
        state = _empty_state()
        state["posted_ids"] = ["a", "b"]
        items = [make_item(id="a"), make_item(id="b")]
        new_items, dup_count = filter_new(items, state)
        assert len(new_items) == 0
        assert dup_count == 2


class TestMarkPosted:
    def test_adds_ids(self):
        state = _empty_state()
        items = [make_item(id="new1"), make_item(id="new2")]
        updated = mark_posted(state, items)
        assert "new1" in updated["posted_ids"]
        assert "new2" in updated["posted_ids"]
        assert updated["last_post"] is not None

    def test_no_duplicate_ids_in_state(self):
        state = _empty_state()
        state["posted_ids"] = ["existing"]
        items = [make_item(id="existing"), make_item(id="new")]
        updated = mark_posted(state, items)
        assert updated["posted_ids"].count("existing") == 1


class TestLoadSaveState:
    def test_roundtrip(self):
        state = _empty_state()
        state["posted_ids"] = ["abc", "def"]
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        ) as f:
            json.dump(state, f)
            tmp_path = Path(f.name)

        loaded = load_state(tmp_path)
        assert loaded["posted_ids"] == ["abc", "def"]
        tmp_path.unlink()

    def test_missing_file_returns_empty(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        state = load_state(missing)
        assert state["posted_ids"] == []
        assert state["version"] == 1


class TestUpdateRunStats:
    def test_accumulates_stats(self):
        state = _empty_state()
        state = update_run_stats(state, collected=10, filtered_expired=2, filtered_score=3, filtered_dup=1)
        assert state["stats"]["total_collected"] == 10
        assert state["stats"]["total_filtered_expired"] == 2
        assert state["stats"]["total_filtered_low_score"] == 3
        assert state["stats"]["total_filtered_duplicate"] == 1
        assert state["last_run"] is not None
