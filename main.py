"""
CLI Entry Point.

Command-line interface for the Adobe Stock Image Generator.
Handles argument parsing, workflow execution (generation, upscaling, metadata),
and logging.
"""
import os
import sys
import argparse
import time
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from src.generator import ImageGenerator
from src.processor import ImageProcessor
from src.metadata import MetadataManager

# pylint: disable=broad-exception-caught

def main(): # pylint: disable=too-many-locals, too-many-statements
    """
    Main function for CLI execution.
    Parses arguments and runs the generation pipeline.
    """
    parser = argparse.ArgumentParser(description="Adobe Stock Image Generator")
    parser.add_argument(
        "--keyword", type=str, required=True, help="Main theme keyword"
    )
    parser.add_argument(
        "--tags", type=str, default="", help="Comma-separated mandatory tags"
    )
    parser.add_argument(
        "--n", type=int, default=10, help="Number of variations (ideas)"
    )
    parser.add_argument(
        "--model", type=str, default="gpt-image-1.5", help="OpenAI Image Model"
    )
    parser.add_argument(
        "--size", type=str, default=None, help="Image size (e.g. 1024x1024)"
    )
    parser.add_argument(
        "--quality", type=str, default=None, help="Image quality (standard or hd)"
    )
    parser.add_argument(
        "--response_format", type=str, default=None, help="Response format (url or b64_json)"
    )
    parser.add_argument(
        "--style", type=str, default="japanese_simple", help="Style type"
    )

    args = parser.parse_args()

    # セットアップ
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("エラー: .env に OPENAI_API_KEY が見つかりません")
        return

    # モジュールの初期化
    generator = ImageGenerator(api_key, model_name=args.model)
    processor = ImageProcessor()
    metadata_mgr = MetadataManager(api_key)

    # ディレクトリ設定
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    # キーワードをフォルダ名用にサニタイズ
    safe_keyword = args.keyword.replace(" ", "_").replace("/", "").replace("\\", "")
    # 出力ディレクトリはルート直下の "タイムスタンプ_キーワード"
    base_output_dir = os.path.join(
        os.getcwd(), f"output/{timestamp}_{safe_keyword}"
    )

    images_dir = os.path.join(base_output_dir, "generated_images")
    upscale_dir = base_output_dir # アップスケール画像はタイムスタンプフォルダ直下
    # ディレクトリ作成
    # 構造:
    # root/
    #   timestamp_keyword/
    #     generated_images/ (生成画像, prompt.csv)
    #     upscaled_xxx.png (アップスケール画像)
    #     submit.csv

    os.makedirs(images_dir, exist_ok=True)

    user_tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    print(f"キーワード '{args.keyword}' でモデル '{args.model}' を使用して生成を開始します")

    # 履歴保存
    command_str = f"python {' '.join(sys.argv)}"
    history_file = "history.md"
    history_content = f"""
## {timestamp} - {args.keyword}
- **Command**: `{command_str}`
- **Model**: {args.model}
- **Tags**: {args.tags}
- **N (Ideas)**: {args.n}
- **Size**: {args.size}
- **Quality**: {args.quality}
- **Style**: {args.style}
- **Output Dir**: {base_output_dir}
"""
    try:
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(history_content)
    except Exception as e:
        print(f"履歴保存エラー: {e}")

    # 1. アイデア生成
    print("画像のアイデアを生成中...")
    ideas = generator.generate_image_description(
        args.keyword, n_ideas=args.n, style=args.style
    )

    csv_data = []

    for i, idea in enumerate(tqdm(ideas, desc="処理中")):
        try:
            # 2. 描画プロンプト生成
            draw_prompt = generator.generate_drawing_prompt(idea)

            # ファイル名設定
            base_name = f"img_{i:03d}"
            raw_filename = f"{base_name}.png"
            raw_path = os.path.join(images_dir, raw_filename)

            # 3. 画像生成
            generator.generate_image(
                prompt=draw_prompt,
                output_path=raw_path,
                size=args.size,
                quality=args.quality,
                response_format=args.response_format
            )

            # 4. アップスケール
            # アップスケールファイル名形式: upscaled_000_YYYY... .png
            time_short = datetime.now().strftime('%Y-%m-%dT%H-%M')
            upscaled_filename = f"upscaled_{i:03d}_{time_short}.png"
            upscaled_path = os.path.join(upscale_dir, upscaled_filename)

            processor.upscale_image(raw_path, upscaled_path)

            # 5. メタデータ生成
            meta = metadata_mgr.get_image_metadata(draw_prompt, user_tags)

            # データ収集
            csv_data.append({
                "filename": raw_filename,
                "upscaled_filename": upscaled_filename,
                "title": meta.get("title", ""),
                "tags": meta.get("tags", ""),
                "category": meta.get("category", 8),
                "prompt": draw_prompt
            })

            # レート制限回避のため待機
            time.sleep(1)

        except Exception as e:
            print(f"アイデア {i} の処理中にエラーが発生しました: {e}")

    # 6. CSV出力
    if not csv_data:
        print("画像が生成されなかったため、CSV出力はスキップされます。")
    else:
        # prompt.csv は generated_images へ
        metadata_mgr.export_csvs(csv_data, upscale_dir)

        # prompt.csv を generated_images に出力する必要がある
        prompt_df = pd.DataFrame(csv_data)[['filename', 'prompt']]
        prompt_df.to_csv(
            os.path.join(images_dir, "prompt.csv"),
            index=False,
            encoding='utf-8-sig',
            errors="ignore"
        )
        # Excel互換性のため utf-8-sig を使用

    print("完了しました！")

if __name__ == "__main__":
    main()
