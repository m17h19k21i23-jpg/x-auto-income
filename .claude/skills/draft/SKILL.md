# Skill: draft — X 投稿テンプレートの管理

## 目的
`app/publish_x.py` の `_TEMPLATES` リストを管理・改善する。

## テンプレートのルール

1. **文字数制限**: 投稿テキスト全体が 280 文字以内（URL は t.co 換算 23 文字）
2. **必須要素**: `{url}` を必ず含む
3. **推奨要素**: `{title}`, `{value}`, `{expires}` のいずれかを含む
4. **禁止**: 虚偽・誇大表現、個人情報の要求、不当な誘導

## 現在のテンプレート

```python
_TEMPLATES = [
    "🎁 {title}が無料！\n{summary}\n⏰ {expires}\n→ {url}",
    "✨ 期間限定｜{title}\n{value}相当が無料配布中\n{summary}\n詳細→ {url}",
    "🔥 お得情報｜{title}\n{summary}\n⏰ {expires}まで\n公式→ {url}",
    "💰 {value}｜{title}\n{summary}\n期間限定キャンペーン\n→ {url}",
    "📢 【無料配布】{title}\n{summary}\n残り: {expires}\n公式サイト→ {url}",
    "⚡ 今だけ無料！{title}\n{summary}\n{expires}まで\n詳細はこちら→ {url}",
]
```

## テンプレート追加手順

1. テンプレート文字列を作成し、最大文字数を計算する
2. `{title}` の最大長（50文字程度）を想定してチェック
3. `_TEMPLATES` リストに追加
4. `python -m pytest tests/test_publish_x.py::TestBuildTweet -v` で動作確認

## 文字数チェック（手動計算式）

```
テンプレート長 - {title}(想定50文字) - {value}(想定10文字)
    - {summary}(想定60文字) - {expires}(想定15文字) - {url}(t.co=23文字)
```

計算結果が 280 以内であること。

## 連続使用防止

`_select_template()` が直近 3 回と異なるテンプレートを選ぶ。
テンプレートが 4 つ以上あれば問題なく機能する。
