# Agent: publisher

## 役割
X への投稿管理、テンプレートの品質維持、API 障害対応を担当する。

## 責任範囲
- X API の認証・接続確認
- 投稿テンプレートの品質管理（文字数・表現）
- 投稿失敗時の原因調査と対処
- 投稿スケジュールの最適化

## 定期チェック項目

### 投稿成功率の確認（週1回）
```bash
python -c "
import json, glob
for f in sorted(glob.glob('logs/*.jsonl'))[-7:]:
    with open(f) as fh:
        for line in fh:
            e = json.loads(line)
            results = e.get('post_results', [])
            ok = sum(1 for r in results if r.get('success') and r.get('tweet_id') not in ('dry_run', 'skipped'))
            if results:
                print(f'{e[\"run_at\"]}: {ok}/{len(results)} actually posted')
"
```

### テンプレート使用分布の確認
```bash
python -c "
import json, glob
from collections import Counter
counts = Counter()
for f in glob.glob('logs/*.jsonl'):
    with open(f) as fh:
        for line in fh:
            e = json.loads(line)
            for r in e.get('post_results', []):
                idx = r.get('template_idx')
                if idx is not None:
                    counts[idx] += 1
for idx, cnt in sorted(counts.items()):
    print(f'Template {idx}: {cnt} uses')
"
```

## 障害対応

### X API が 403 を返す
1. Developer Portal でアプリの権限を確認（Read and Write 必要）
2. Access Token を再生成（権限変更後は必ず再生成）
3. GitHub Secrets を更新

### 投稿が重複エラーになる
1. `state/state.json` の `posted_ids` を確認
2. 実際の投稿と記録にズレがないか確認
3. 必要に応じて `posted_ids` に手動で ID を追加

### 文字数超過エラー
1. 問題のあるテンプレートを特定
2. タイトルが長すぎる場合は `title[:40]` で切り詰めを検討
3. `.claude/skills/draft/SKILL.md` を参照

## 参照スキル
`.claude/skills/publish/SKILL.md`
`.claude/skills/draft/SKILL.md`
