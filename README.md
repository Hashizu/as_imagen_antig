# Adobe Stock 画像生成ツール (GUI版)

Adobe Stockへの投稿用に、OpenAIのAPIを利用して画像を生成、選別、アップスケール、およびメタデータ（タイトル・タグ）の作成を自動化するツールです。
新しく **GUI (Streamlit)** が実装され、ブラウザ上で直感的に操作できるようになりました。

## 機能

1.  **GUI操作**: ブラウザ上で生成から選別、登録まで完結します。
2.  **アイデア生成**: キーワードに基づいて、複数の画像アイデア（説明）を生成します。
3.  **画像生成**: DALL-E 3 等を使用して画像を生成します（生成時は高速化のためアップスケールしません）。
4.  **ギャラリー選別**: 生成した画像を一覧表示し、「登録」するか「除外」するかを選別できます。アプリを閉じても状態は保存されます。
5.  **遅延アップスケール**: 「登録」ボタンを押した画像のみ、OpenCVを使用して2倍に高画質化します。
6.  **メタデータ生成**: Adobe Stockに適したタイトル、カテゴリー、タグ（日本語）を自動生成します。
7.  **一括出力**: 登録した画像をまとめて `submit.csv` と共に出力します。

## 動作環境

- Windows
- Python 3.12 以上
- 推奨: 仮想環境 (`.venv`) の使用

## セットアップ

1.  **仮想環境の作成と有効化**:
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    ```

2.  **依存ライブラリのインストール**:
    ```bash
    pip install -r requirements.txt
    pip install streamlit
    ```

3.  **環境変数の設定**:
    `.env` ファイルを作成し、OpenAIとAWSの認証情報を設定してください。
    ```text
    OPENAI_API_KEY=your_openai_api_key
    AWS_ACCESS_KEY_ID=your_aws_access_key
    AWS_SECRET_ACCESS_KEY=your_aws_secret_key
    S3_BUCKET_NAME=your_s3_bucket_name
    AWS_REGION=ap-northeast-1
    ```

## 使い方 (GUI)

以下のコマンドでアプリケーションを起動します。

```bash
streamlit run app.py
```

または、デスクトップ等に配置可能な **`launch_app.bat`** をダブルクリックすることでも起動できます。

ブラウザが自動的に開き、以下のタブから操作できます。

### 1. 🚀 Generate (生成タブ)
*   画像生成のパラメータ（キーワード、枚数、モデルなど）を入力して生成します。
*   **Mandatory Tags**: 生成されるすべての画像のメタデータに必ず含めたいタグがある場合はここに入力します（カンマ区切り）。
*   生成された画像は **AWS S3** (`output/日時_キーワード/generated_images/`) に保存されます。

### 2. 🖼️ Gallery & Submit (ギャラリー・登録タブ)
*   **タブ切り替え**: 以下の3つのタブで画像を管理します。
    *   **Unprocessed (未処理)**: 新しく生成された画像。ここで「登録」か「除外」を選別します。
    *   **Registered (登録済)**: 提出用に選ばれた画像。ここから「Revert」で未処理に戻せます。
    *   **Excluded (除外)**: 不要と判断された画像。ここから「Revert」で未処理に戻せます。
*   **画像選択**: 画像下のチェックボックスで選択します。
*   **一括操作**:
    *   **📤 Register Selected**: 選択した画像を登録します（Unprocessedタブ）。ここで初めて**アップスケール**と**CSV作成**が行われ（S3上で処理）、ZIPファイルのダウンロード準備が整います。
    *   **🗑️ Exclude Selected**: 選択した画像を除外します（Unprocessedタブ）。
    *   **↩️ Revert**: 登録済みや除外された画像を、再度「未処理」ステータスに戻します。
*   **ダウンロード**: 登録完了後、サイドバーに表示される **「📦 Download Last Submission」** ボタンから一括ダウンロードできます。

### 出力ファイル (提出用)

登録処理が完了すると、ZIPファイルがダウンロードされます。解凍すると以下の構成になっています。

```
submission_YYYYMMDD_HHMMSS/
├── upscaled_000_....png     # アップスケールされた提出用画像
├── ...
└── submit.csv               # Adobe Stock提出用CSV（メタデータ含む）
```

- **submit.csv**: これをAdobe StockのContributorポータルでアップロードしてください。

## 開発者向け情報

### ディレクトリ構成 (AWS S3)
本アプリケーションはローカルストレージを使用せず、すべてのデータを S3 に保存します。

- `output/`: 生成された生画像、アップスケール画像 (`upscaled_...`)
- `data/image_status.json`: 画像のステータス管理DB
- `history.md`: 実行履歴

### ソースコード構成 (`src/`)
- `generator.py`: 画像生成 (S3 Upload)
- `processor.py`: 画像処理・アップスケール (S3 Download -> Process -> S3 Upload)
- `metadata.py`: メタデータ生成
- `state_manager.py`: 状態管理 (S3 Sync)
- `submission_manager.py`: 登録・ZIP作成 (On-the-fly)
- `storage.py`: Aws S3 操作ラッパー

## 実行履歴
実行記録は S3 上の `history.md` に追記されます。

## 注意事項
- 生成にはOpenAI APIの利用料がかかります。
- 生成されたコンテンツの著作権や利用規約については、OpenAIおよびAdobe Stockの規約に従ってください。
