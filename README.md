# Epic Games 無料配布・セール速報

Epic Games Store の無料配布・値下げ情報を自動収集し、X（旧Twitter）に速報投稿しながら GitHub Pages に一覧ページを公開するシステムです。

## 機能

- Epic Games Store 公式 API から無料配布・セール情報を自動収集
- 重複投稿防止（state/state.json で管理）
- スコアリングによる品質フィルタリング
- GitHub Actions で定期実行（6時間ごと）
- GitHub Pages で「Epic Games 無料配布・セール速報」一覧ページを公開
- dry-run モードでローカルテスト可能
- 収益リンクスロット内蔵（初期は OFF）

## セットアップ（Windows）

### 1. 前提条件

- Python 3.11 以上（[python.org](https://python.org) からインストール）
- Git for Windows（[git-scm.com](https://git-scm.com) からインストール）
- X Developer アカウント（[developer.twitter.com](https://developer.twitter.com)）

### 2. リポジトリのクローン

```cmd
git clone https://github.com/あなたのユーザー名/x-auto-income.git
cd x-auto-income
```

### 3. Python 仮想環境のセットアップ

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env.example` をコピーして `.env` を作成します：

```cmd
copy .env.example .env
```

`.env` を編集して値を入れます：

```env
# X (Twitter) API 認証情報
X_API_KEY=your_api_key_here
X_API_SECRET=your_api_secret_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_SECRET=your_access_secret_here

# 投稿制御
POST_ENABLED=false        # true にすると実際に X に投稿する
MONETIZATION_ENABLED=false  # true にすると収益リンクを表示する

# 動作設定
LOG_LEVEL=INFO
MIN_SCORE=0.5             # この値以上のスコアのみ投稿対象
```

> ⚠️ `.env` は絶対にコミットしないでください。`.gitignore` に含まれています。

### 5. ローカルでの動作確認（dry-run）

```cmd
# モックデータで動作確認（実際の API 呼び出しなし）
python app/main.py --dry-run

# 実際の API からデータ収集（投稿はしない）
python app/main.py --dry-run --no-mock
```

### 6. テストの実行

```cmd
python -m pytest tests/ -v
```

### 7. 手動で投稿を実行

```cmd
# POST_ENABLED=true にしてから実行
python app/main.py --post
```

## GitHub Actions の設定

### Secrets の登録

GitHub リポジトリの **Settings > Secrets and variables > Actions** で以下を登録：

| Secret 名 | 説明 |
|-----------|------|
| `X_API_KEY` | X API キー |
| `X_API_SECRET` | X API シークレット |
| `X_ACCESS_TOKEN` | X アクセストークン |
| `X_ACCESS_SECRET` | X アクセストークンシークレット |

### GitHub Pages の有効化

1. GitHub リポジトリの **Settings > Pages** を開く
2. Source を **GitHub Actions** に設定
3. ワークフローを手動実行して初回デプロイ

### Variables の設定（任意）

**Settings > Secrets and variables > Actions > Variables** で設定：

| Variable 名 | デフォルト | 説明 |
|------------|----------|------|
| `POST_ENABLED` | `false` | X 投稿を有効にする |
| `MONETIZATION_ENABLED` | `false` | 収益リンクを表示する |
| `MIN_SCORE` | `0.5` | 最低スコア閾値 |

## ディレクトリ構成

```
x-auto-income/
├── app/
│   ├── collect.py       # データ収集
│   ├── normalize.py     # データ正規化
│   ├── score.py         # スコアリング・フィルタリング
│   ├── dedupe.py        # 重複排除
│   ├── render_site.py   # サイト生成
│   ├── publish_x.py     # X 投稿
│   ├── main.py          # エントリーポイント
│   └── templates/       # Jinja2 テンプレート
├── state/
│   └── state.json       # 投稿済み ID 管理
├── site/                # 生成された静的サイト（GitHub Pages）
├── logs/                # 監査ログ
├── tests/               # テスト
├── .github/workflows/   # GitHub Actions
└── .claude/             # Claude Code スキル・エージェント定義
```

## 新しいデータソースの追加（Epic Games 関連のみ）

1. `.claude/skills/collect/SKILL.md` を参照
2. `app/collect.py` に新しい Collector クラスを追加（公式 API/RSS のみ）
3. `@register` デコレーターで登録
4. `tests/` にテストを追加

## 収益化の有効化

1. `MONETIZATION_ENABLED=true` を環境変数またはGitHub Variablesに設定
2. `app/templates/index.html.j2` の `<!-- MONETIZATION SLOT -->` コメントを探して収益リンクを配置

## トラブルシューティング

**Q: `ModuleNotFoundError` が出る**
A: 仮想環境が有効化されているか確認 → `.venv\Scripts\activate`

**Q: X API エラーが出る**
A: Developer Portal でアプリの Read/Write 権限を確認し、`X_ACCESS_TOKEN` を再生成

**Q: GitHub Actions が失敗する**
A: Actions タブでログを確認し、Secrets が正しく設定されているか確認

**Q: サイトが更新されない**
A: Pages の設定で Source が「GitHub Actions」になっているか確認
