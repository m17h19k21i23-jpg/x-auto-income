# Skill: collect — 新しいデータソースの追加

## 目的
`app/collect.py` に新しい公式データソースの Collector を追加する。

## 追加前チェックリスト

1. **公式 API または RSS が存在するか**
   - 公式ドメインからのデータのみ受け付ける
   - スクレイピングではなく API/RSS を優先する
   - 利用規約で自動アクセスが禁止されていないか確認する

2. **レート制限の確認**
   - API のレート制限を調べ、`REQUEST_TIMEOUT = 15` で安全か確認する
   - 必要に応じてバックオフ処理を追加する

3. **返すデータの形式**
   - `title`, `url`, `value`, `expires_at`, `summary`, `category`, `source` を含むこと
   - `url` は公式ドメインの直接リンクであること

## 実装手順

```python
# app/collect.py に追加

@register
class NewSourceCollector(BaseCollector):
    name = "new_source"  # 一意の名前
    API_URL = "https://official-source.example.com/api/deals"

    def collect(self) -> list[dict[str, Any]]:
        try:
            resp = requests.get(self.API_URL, timeout=self.REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("%s API error: %s", self.name, exc)
            return []

        items = []
        for entry in data.get("items", []):
            items.append({
                "title": entry.get("name", "").strip(),
                "url": entry.get("official_url", "").strip(),
                "source": self.name,
                "summary": entry.get("description", "")[:120],
                "value": entry.get("discount", ""),
                "expires_at": entry.get("end_date"),  # ISO 8601 or None
                "category": "game",  # game / software / service / other
            })
        return items
```

## テストの追加

`tests/test_collect.py` を作成して以下を確認する:
- コレクターが `list[dict]` を返す
- API エラー時に空リストを返す（例外を伝播させない）
- 返す各アイテムに `title`, `url`, `source` が含まれる

## 注意

- `MockCollector` のテストデータも更新して新しいソースの形式をカバーする
- 本番環境での初回実行は `workflow_dispatch` で `dry_run=true` を使う
