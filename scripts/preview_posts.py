"""
preview_posts.py — Dealify 案件の投稿文プレビュー（POST_ENABLED=false / dry-run 前提）

使い方:
  python scripts/preview_posts.py
  python scripts/preview_posts.py --top 3

出力:
  各案件タイトル・文字数・生成された投稿文テキストを標準出力に表示する。
  ファイル書き込み・X 投稿は一切行わない。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Windows コンソールで絵文字・日本語が化けないよう UTF-8 を強制する
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# プロジェクトルートを import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.normalize import normalize_all
from app.publish_x import _build_tweet, _count_tweet_length, _pages_item_url

DATA_PATH = Path(__file__).parent.parent / "data" / "deals_static.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Dealify 投稿文プレビュー")
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="上位 N 件のみ表示（0 = 全件）",
    )
    args = parser.parse_args()

    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} が見つかりません", file=sys.stderr)
        sys.exit(1)

    raw_items = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    items, stats = normalize_all(raw_items)

    target = items[: args.top] if args.top > 0 else items
    print(f"=== Dealify 投稿文プレビュー（{len(target)}/{len(items)} 件）===")
    print()

    ok_count = 0
    warn_count = 0
    for i, item in enumerate(target, 1):
        text = _build_tweet(item, 0)
        url = _pages_item_url(item) or ""
        length = _count_tweet_length(text, url)
        over = length > 280

        status = "⚠ 文字数超過" if over else "OK"
        if over:
            warn_count += 1
        else:
            ok_count += 1

        print(f"--- [{i}] {item['title']}  slug={item.get('slug', '(なし)')}  {length}文字  {status} ---")
        print(text)
        print()

    print(f"=== 結果: OK {ok_count}件 / 文字数超過 {warn_count}件 ===")


if __name__ == "__main__":
    main()
