# Skill: score — スコアリングの調整

## 目的
`app/score.py` のスコアリングロジックを調整・改善する。

## 現在のスコアリング構成

| 項目 | 最大点 | 関数 |
|------|--------|------|
| 価値の明確さ（無料/¥X/%OFF） | 0.30 | `_score_value_clarity` |
| 価値の大きさ（金額・割引率） | 0.15 | `_score_value_magnitude` |
| 期限の緊急性 | 0.25 | `_score_deadline` |
| カテゴリーボーナス | 0.20 | `_score_category` |
| 要約の充実度 | 0.10 | `_score_summary` |
| **合計** | **1.00** | — |

## 調整ガイドライン

### スコアを上げたい場合
- 特定カテゴリーの `_CATEGORY_BONUS` 値を増やす
- 特定の価値表現（例: "完全無料"）を `_score_value_clarity` に追加する

### スコアを下げたい場合
- `DEFAULT_MIN_SCORE` を上げる（環境変数 `MIN_SCORE` でも変更可）
- 特定ソースのスコアにペナルティを加える

### 新しいシグナルを追加する場合

```python
def _score_new_signal(item: Item) -> float:
    # 例: タイトルに特定キーワードが含まれるボーナス
    if any(kw in item["title"] for kw in ["限定", "先着"]):
        return 0.05
    return 0.0

# score_item() 関数内に追加:
def score_item(item: Item) -> Item:
    s = (
        _score_value_clarity(item["value"])
        + _score_value_magnitude(item["value"])
        + _score_deadline(item["expires_at"])
        + _score_category(item["category"])
        + _score_summary(item["summary"])
        + _score_new_signal(item)  # ← 追加
    )
    item["score"] = round(min(s, 1.0), 4)
    return item
```

## テスト

スコア変更後は必ず `python -m pytest tests/test_score.py -v` を実行する。

特に以下を確認する:
- `test_score_capped_at_one` — スコアが 1.0 を超えないか
- `test_score_non_negative` — スコアが負にならないか
- 実際のデータで `MIN_SCORE=0.5` の閾値が適切か
