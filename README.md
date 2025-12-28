# Adobe Stock 画像生成ツール

Adobe Stockへの投稿用に、OpenAIのAPIを利用して画像を生成、アップスケール、およびメタデータ（タイトル・タグ）の作成を自動化するツールです。

## 機能

1.  **アイデア生成**: キーワードに基づいて、複数の画像アイデア（説明）を生成します。
2.  **画像生成**: DALL-E 3 等を使用して画像を生成します。
3.  **アップスケール**: OpenCVを使用して画像を2倍に高画質化します。
4.  **メタデータ生成**: 生成された画像に対して、Adobe Stockに適したタイトル、カテゴリー、タグ（日本語）を自動生成します。
5.  **CSV出力**: Adobe Stockへの一括登録用の `submit.csv` と、プロンプト記録用の `prompt.csv` を出力します。

## 動作環境

- Windows
- Python 3.12 以上
- 推奨: 仮想環境 (`.venv`) の使用

## セットアップ

1.  **リポジトリの準備**:
    ```bash
    # 必要なファイルを配置してください
    ```

2.  **仮想環境の作成と有効化**:
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    ```

3.  **依存ライブラリのインストール**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **環境変数の設定**:
    `.env` ファイルを作成し、OpenAIのAPIキーを設定してください。
    ```text
    OPENAI_API_KEY=your_api_key_here
    ```

## 使い方

`main.py` を実行して画像生成を開始します。
仮想環境を使用する場合は、実行前に有効化するか、仮想環境内のPythonを直接指定してください。

```bash
# 仮想環境の有効化 (Windows)
.venv\Scripts\activate

# または直接実行
.venv\Scripts\python main.py ...
```

### 基本的なコマンド

```bash
python main.py --keyword "猫" --tags "かわいい,ペット" --n 5
```

### オプション引数

- `--keyword` (必須): 画像のメインテーマ（英語または日本語）。フォルダ名にも使用されます。
- `--tags`: 必須で含めたいタグ。カンマ区切りで指定（例: `"風景,自然,青"`）。
- `--n`: 生成するバリエーションの数（デフォルト: `10`）。
- `--model`: 使用する画像生成モデル（デフォルト: `gpt-image-1.5`）。
- `--size`: 生成画像のサイズ（デフォルト: `1024x1024`）。
- `--quality`: 画質設定（`standard` または `hd`、デフォルト: `standard`）。
- `--response_format`: レスポンス形式（`url` または `b64_json`、デフォルト: `url`）。
- `--style`: 画像のスタイル（デフォルト: `japanese_simple`）。

### 実行例

**10枚の猫の画像を生成する場合:**
```bash
python main.py --keyword "cat" --n 10
```

**モデルを指定して実行する場合:**
```bash
python main.py --keyword "future city" --model "dall-e-3"
```

## 出力ファイル

実行すると、./output/に `YYYY-mm-ddXH-M-S_キーワード` という形式のフォルダが作成されます。

**フォルダ構成:**
```
YYYY-mm-dd_HH-MM-SS_keyword/
├── generated_images/        # 生成された元画像
│   ├── img_000.png
│   ├── ...
│   └── prompt.csv           # 画像ごとのプロンプト一覧
├── upscaled_000_....png     # アップスケールされた提出用画像
├── ...
└── submit.csv               # Adobe Stock提出用CSV（メタデータ含む）
```

- **submit.csv**: そのままAdobe StockのCONTRIBUTORポータルでCSVアップロードに使用できます。
- **upscaled_*.png**: Adobe Stockにアップロードする画像ファイルです。

## 実行履歴

実行ごとに `history.md` に以下の情報が追記されます：
- タイムスタンプ
- 使用したモデル、パラメータ
- 出力先ディレクトリ

## 注意事項

- 生成にはOpenAI APIの利用料がかかります。
- 生成されたコンテンツの著作権や利用規約については、OpenAIおよびAdobe Stockの規約に従ってください。
