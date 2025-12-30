"""
Submission Manager Module.

Handles the submission process including upscaling,
metadata generation, and packaging for Adobe Stock.
"""
import os
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from tqdm import tqdm

from src.processor import ImageProcessor
from src.metadata import MetadataManager
from src.state_manager import StateManager, STATUS_REGISTERED

class SubmissionManager:
    """
    Class to upscale selected images, organize them into a submission folder,
    and generate the required CSV.
    """
    def __init__(self, api_key: str):
        self.processor = ImageProcessor()
        self.metadata_mgr = MetadataManager(api_key)
        self.state_mgr = StateManager()

    def process_submission(self, selected_images: List[Dict], keyword: str = "batch"):
        """
        Execute the submission process for a list of selected images.

        Args:
            selected_images (List[Dict]): List of image dictionaries from StateManager.
                                          Must contain 'path' key with relative path.
            keyword (str): Identifier used for the folder name.

        Returns:
            str: Path to the created submission folder.
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
                result = self._process_single_image(idx, img_info, submission_dir)
                if result:
                    csv_data.append(result['csv_entry'])
                    processed_file_paths.append(result['rel_path'])

            except Exception as e: # pylint: disable=broad-exception-caught
                print(f"Error processing {img_info.get('path')}: {e}")

        # 4. CSV出力
        if csv_data:
            self.metadata_mgr.export_csvs(csv_data, submission_dir)

        # 5. ステータス更新 (Team A連携)
        if processed_file_paths:
            self.state_mgr.update_status(processed_file_paths, STATUS_REGISTERED)

        print(f"提出バッチ処理完了: {submission_dir}")
        return submission_dir

    def _process_single_image(
        self,
        idx: int,
        img_info: Dict,
        submission_dir: str
    ) -> Optional[Dict]:
        """
        Process a single image: upscale, generate metadata, and prepare CSV entry.
        """
        rel_path = img_info['path']
        abs_path = os.path.abspath(rel_path)

        if not os.path.exists(abs_path):
            print(f"Skipping missing file: {abs_path}")
            return None

        # ファイル名生成
        original_basename = os.path.splitext(os.path.basename(abs_path))[0]
        new_filename = f"upscaled_{idx:03d}_{original_basename}.png"
        output_path = os.path.join(submission_dir, new_filename)

        # 2. アップスケール実行
        self.processor.upscale_image(abs_path, output_path)

        # 3. メタデータ取得
        prompt = img_info.get('prompt', "")
        if not prompt:
            prompt = self._find_prompt_from_source(abs_path)

        # タグ生成
        stored_tags_str = img_info.get('tags', "")
        stored_tags = (
            [t.strip() for t in stored_tags_str.split(",") if t.strip()]
            if stored_tags_str else []
        )

        meta = self.metadata_mgr.get_image_metadata(prompt, user_tags=stored_tags)

        return {
            "csv_entry": {
                "filename": os.path.basename(abs_path),
                "upscaled_filename": new_filename,
                "title": meta.get("title", ""),
                "tags": meta.get("tags", ""),
                "category": meta.get("category", 8),
                "prompt": prompt
            },
            "rel_path": rel_path
        }

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
        except Exception: # pylint: disable=broad-exception-caught
            pass
        return ""
