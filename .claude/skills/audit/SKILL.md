# Skill: audit — 監査ログの確認と分析

## ログの場所

`logs/YYYY-MM-DD.jsonl` — JSON Lines 形式（1行1エントリ）

## ログエントリの構造

```json
{
  "run_at": "2026-03-27T06:00:00Z",
  "dry_run": false,
  "use_mock": false,
  "min_score": 0.5,
  "max_posts": 3,
  "raw_count": 5,
  "normalize": {"total": 5, "valid": 3, "dropped": 2},
  "score_dropped": 1,
  "dup_count": 0,
  "post_results": [
    {
      "item_id": "abc123",
      "success": true,
      "tweet_id": "1234567890",
      "text": "🎁 テストゲームが無料！...",
      "length": 120,
      "template_idx": 2
    }
  ]
}
```

## よくある分析タスク

### 投稿成功率の確認
```bash
# 各実行の投稿結果を集計
python -c "
import json, glob
for f in sorted(glob.glob('logs/*.jsonl')):
    with open(f) as fh:
        for line in fh:
            entry = json.loads(line)
            results = entry.get('post_results', [])
            ok = sum(1 for r in results if r.get('success'))
            print(f'{entry[\"run_at\"]}: {ok}/{len(results)} posted')
"
```

### 除外率の確認（データ品質チェック）
```bash
python -c "
import json, glob
for f in sorted(glob.glob('logs/*.jsonl')):
    with open(f) as fh:
        for line in fh:
            e = json.loads(line)
            n = e.get('normalize', {})
            print(f'{e[\"run_at\"]}: raw={e.get(\"raw_count\",0)} valid={n.get(\"valid\",0)} score_drop={e.get(\"score_dropped\",0)} dup={e.get(\"dup_count\",0)}')
"
```

## 異常検知のポイント

- `raw_count == 0`: コレクターが全件失敗（API 障害の可能性）
- `normalize.dropped / normalize.total > 0.8`: データ品質が低い
- `post_results` に `error` が多い: X API 認証エラーの可能性
- `dup_count` が毎回高い: 新規情報が少ない（ソースの見直しを検討）
