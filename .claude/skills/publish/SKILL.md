# Skill: publish — X API セットアップと投稿管理

## X Developer Portal セットアップ

### 1. アプリの作成
1. https://developer.twitter.com/en/portal/dashboard にアクセス
2. 「+ Create Project」→ プロジェクト作成
3. 「+ Add App」→ アプリ作成
4. App permissions を **Read and Write** に設定（デフォルトは Read only）

### 2. キーの取得
「Keys and tokens」タブから取得:
- **API Key** → `X_API_KEY`
- **API Key Secret** → `X_API_SECRET`
- **Access Token** → `X_ACCESS_TOKEN`（ユーザー認証後に生成）
- **Access Token Secret** → `X_ACCESS_SECRET`（ユーザー認証後に生成）

> Access Token は「Generate」ボタンで生成。**Read and Write** 権限で生成すること。

### 3. GitHub Secrets への登録
リポジトリの Settings > Secrets and variables > Actions:
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_SECRET`

## 投稿レートリミット

X API v2 の無料プラン:
- 投稿: 17 ツイート/24時間
- 月間: 500 ツイート/月

`MAX_POSTS_PER_RUN=3` + 6時間ごと実行 = 最大 12 投稿/日（余裕あり）

## トラブルシューティング

### `403 Forbidden`
- App permissions が Read and Write になっているか確認
- Access Token を **権限変更後に再生成**（変更前のトークンは無効）

### `401 Unauthorized`
- 4つのキーすべてが正しいか確認
- `X_ACCESS_TOKEN` と `X_ACCESS_SECRET` が一致しているか確認

### 同じ内容の投稿エラー
- X は重複内容の投稿を弾く（`403 duplicate content`）
- テンプレートのバリエーションが機能しているか確認
- `state.json` に正しく記録されているか確認

## 投稿前の手動テスト

```bash
# 実際に投稿せず、テキストを確認する
POST_ENABLED=false python app/main.py --post

# 1件だけ実際に投稿する
MAX_POSTS_PER_RUN=1 POST_ENABLED=true python app/main.py --post
```
