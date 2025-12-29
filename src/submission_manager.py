# src/submission_manager.py
import os
import shutil
import glob
from typing import List, Dict
from datetime import datetime
import pandas as pd
from tqdm import tqdm

from src.processor import ImageProcessor
from src.metadata import MetadataManager
from src.state_manager import StateManager, STATUS_REGISTERED

class SubmissionManager:
    """
    選択された画像をアップスケールし、提出用フォルダにまとめ、CSVを出力するクラス。
    """
    def __init__(self, api_key: str):
        self.processor = ImageProcessor()
        self.metadata_mgr = MetadataManager(api_key)
        self.state_mgr = StateManager()

    def process_submission(self, selected_images: List[Dict], keyword: str = "batch"):
        """
        選択された画像リストを受け取り、提出プロセスを実行する。
        
        Args:
            selected_images (List[Dict]): StateManagerから取得した画像辞書のリスト。
                                          'path' キーに相対パスが含まれていること。
            keyword (str): フォルダ名に使用する識別子。
        
        Returns:
            str: 作成された提出フォルダのパス
        """
        if not selected_images:
            return None

        # 1. 提出用ディレクトリ作成
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        safe_keyword = keyword.replace(" ", "_").replace("/", "")
        submission_dir = os.path.join("submissions", f"{timestamp}_{safe_keyword}")
        os.makedirs(submission_dir, exist_ok=True)

        csv_data = []
        processed_file_paths = []

        print(f"提出処理を開始します: {len(selected_images)}枚")

        for idx, img_info in enumerate(tqdm(selected_images, desc="Upscaling & Copying")):
            try:
                rel_path = img_info['path']
                abs_path = os.path.abspath(rel_path)
                
                if not os.path.exists(abs_path):
                    print(f"Skipping missing file: {abs_path}")
                    continue

                # ファイル名生成: upscaled_KEYWORD_001.png
                # ユニーク性を保つため、元のファイル名を含めるか、連番を振る
                # ここでは連番と元の名前を組み合わせる
                original_basename = os.path.splitext(os.path.basename(abs_path))[0]
                new_filename = f"upscaled_{idx:03d}_{original_basename}.png"
                output_path = os.path.join(submission_dir, new_filename)

                # 2. アップスケール実行
                self.processor.upscale_image(abs_path, output_path)

                # 3. メタデータ取得 (プロンプトはDBまたはCSVから取得済みと仮定)
                # StateManagerのscanでpromptが取得できている場合がある
                prompt = img_info.get('prompt', "")
                
                # もしpromptが空なら、元のフォルダのprompt.csvを探しに行く（念のため）
                if not prompt:
                    prompt = self._find_prompt_from_source(abs_path)

                # タグ生成 (MetadataManager利用)
                # DBから保存されたタグを取得
                stored_tags_str = img_info.get('tags', "")
                stored_tags = [t.strip() for t in stored_tags_str.split(",") if t.strip()] if stored_tags_str else []
                
                # MetadataManagerに渡す
                meta = self.metadata_mgr.get_image_metadata(prompt, user_tags=stored_tags)

                csv_data.append({
                    "filename": os.path.basename(abs_path), # 元ファイル名
                    "upscaled_filename": new_filename,      # 提出用アップスケールファイル名
                    "title": meta.get("title", ""),
                    "tags": meta.get("tags", ""),
                    "category": meta.get("category", 8),
                    "prompt": prompt
                })
                
                processed_file_paths.append(rel_path)

            except Exception as e:
                print(f"Error processing {rel_path}: {e}")

        # 4. CSV出力
        if csv_data:
            self.metadata_mgr.export_csvs(csv_data, submission_dir)

        # 5. ステータス更新 (Team A連携)
        if processed_file_paths:
            self.state_mgr.update_status(processed_file_paths, STATUS_REGISTERED)

        print(f"提出バッチ処理完了: {submission_dir}")
        return submission_dir

    def _find_prompt_from_source(self, image_path: str) -> str:
        """元のフォルダのprompt.csvからプロンプトを再取得（予備）"""
        try:
            dir_path = os.path.dirname(image_path)
            csv_path = os.path.join(dir_path, "prompt.csv")
            if os.path.exists(csv_path):
                filename = os.path.basename(image_path)
                df = pd.read_csv(csv_path)
                row = df[df['filename'] == filename]
                if not row.empty:
                    return row.iloc[0]['prompt']
        except:
            pass
        return ""
