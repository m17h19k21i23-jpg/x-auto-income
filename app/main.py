"""
main.py — エントリーポイント。

使い方:
  python app/main.py --dry-run           # モックデータで動作確認（投稿なし）
  python app/main.py --dry-run --no-mock # 実 API 収集（投稿なし）
  python app/main.py --post              # 本番実行（POST_ENABLED=true 必要）

環境変数（.env または GitHub Variables）:
  POST_ENABLED          true/false
  MONETIZATION_ENABLED  true/false
  MIN_SCORE             float（デフォルト 0.5）
  MAX_POSTS_PER_RUN     int（デフォルト 3）
  LOG_LEVEL             DEBUG/INFO/WARNING/ERROR
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# .env 読み込み（存在する場合のみ）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.collect import collect_all
from app.normalize import normalize_all
from app.score import score_and_filter
from app.dedupe import filter_new, load_state, mark_posted, save_state, update_run_stats
from app.render_site import render
from app.publish_x import post_items

LOGS_DIR = Path(__file__).parent.parent / "logs"


def setup_logging(level: str = "INFO") -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    # Windows の CP932 コンソールで絵文字が化けないよう UTF-8 を強制する
    import io
    stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    logging.basicConfig(level=numeric, handlers=[handler])


def write_audit_log(entry: dict) -> None:
    """logs/YYYY-MM-DD.jsonl に監査ログを追記する。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = LOGS_DIR / f"{today}.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="X 自動投稿 + 情報ページ自動更新システム"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="サイト生成のみ（X 投稿なし・state 変更なし）",
    )
    mode.add_argument(
        "--post",
        action="store_true",
        help="本番実行（POST_ENABLED=true の場合 X に投稿）",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="dry-run でも実際の API からデータ収集する",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        help="収集するソース名を限定する（例: --sources epic_games_free）",
    )
    return parser.parse_args()


def run(dry_run: bool, use_mock: bool, sources: list[str] | None = None) -> int:
    """
    メイン処理。

    Returns:
        終了コード（0=成功, 1=エラー）
    """
    logger = logging.getLogger("main")
    min_score = float(os.getenv("MIN_SCORE", "0.5"))
    max_posts = int(os.getenv("MAX_POSTS_PER_RUN", "3"))

    audit: dict = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": dry_run,
        "use_mock": use_mock,
        "min_score": min_score,
        "max_posts": max_posts,
    }

    # 1. 収集
    logger.info("=== Step 1: Collect ===")
    raw_items = collect_all(sources=sources, use_mock=use_mock)
    audit["raw_count"] = len(raw_items)
    logger.info("Collected %d raw items", len(raw_items))

    # 2. 正規化
    logger.info("=== Step 2: Normalize ===")
    items, norm_stats = normalize_all(raw_items)
    audit["normalize"] = norm_stats

    # 3. スコアリング
    logger.info("=== Step 3: Score & Filter ===")
    scored_items, score_dropped = score_and_filter(items, min_score=min_score)
    audit["score_dropped"] = score_dropped
    logger.info("%d items passed score filter", len(scored_items))

    # 4. state 読み込み + 重複排除
    logger.info("=== Step 4: Dedupe ===")
    state = load_state()
    new_items, dup_count = filter_new(scored_items, state)
    audit["dup_count"] = dup_count
    logger.info("%d new items after deduplication", len(new_items))

    # 5. サイト生成
    logger.info("=== Step 5: Render Site ===")
    try:
        render(scored_items, dry_run=dry_run)
    except Exception as exc:
        logger.error("Site render failed: %s", exc)
        audit["render_error"] = str(exc)

    # 6. 投稿
    post_results: list[dict] = []
    if new_items:
        logger.info("=== Step 6: Publish to X ===")
        post_results = post_items(new_items, max_posts=max_posts, dry_run=dry_run)
        audit["post_results"] = post_results

        posted_items = [
            item
            for item, result in zip(new_items, post_results)
            if result.get("success") and result.get("tweet_id") not in (None, "skipped")
        ]

        if posted_items and not dry_run:
            state = mark_posted(state, posted_items)
    else:
        logger.info("No new items to post.")
        audit["post_results"] = []

    # 7. state 更新・保存
    state = update_run_stats(
        state,
        collected=len(raw_items),
        filtered_expired=norm_stats.get("dropped", 0),
        filtered_score=score_dropped,
        filtered_dup=dup_count,
    )

    if not dry_run:
        save_state(state)
        logger.info("State saved.")
    else:
        logger.info("[dry-run] State not saved.")

    # 8. 監査ログ
    write_audit_log(audit)
    logger.info("Audit log written.")

    # サマリー
    logger.info(
        "=== Done: raw=%d normalize_ok=%d score_ok=%d new=%d posted=%d ===",
        len(raw_items),
        len(items),
        len(scored_items),
        len(new_items),
        sum(1 for r in post_results if r.get("success")),
    )

    return 0


def main() -> None:
    args = parse_args()
    log_level = os.getenv("LOG_LEVEL", "INFO")
    setup_logging(log_level)

    dry_run = args.dry_run
    # --post でも mock を使いたい場合は明示的に --no-mock を渡さなければならない
    # --dry-run のデフォルトは mock を使う（--no-mock で無効化）
    if dry_run:
        use_mock = not args.no_mock
    else:
        use_mock = False  # --post では常に実 API

    sys.exit(run(dry_run=dry_run, use_mock=use_mock, sources=args.sources))


if __name__ == "__main__":
    main()
