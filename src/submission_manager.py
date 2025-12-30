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

    def process_submission(self, selected_images: List[Dict], keyword: str = "batch"): # pylint: disable=too-many-locals
        """
        Execute the submission process for a list of selected images on S3.
        Creates a ZIP file containing upscaled images and submit.csv.

        Args:
            selected_images (List[Dict]): List of image dictionaries from StateManager.
            keyword (str): Identifier used for naming.

        Returns:
            bytes: ZIP file content.
        """
        if not selected_images:
            return None

        from src.storage import S3Manager
        import zipfile
        import io
        
        s3 = S3Manager()
        
        # 提出用一時ディレクトリパス (S3 Key prefix)
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        safe_keyword = keyword.replace(" ", "_").replace("/", "")
        submission_prefix = f"submissions/{timestamp}_{safe_keyword}" # S3 prefix only

        csv_data = []
        processed_file_paths = []
        
        # ZIPバッファ作成
        zip_buffer = io.BytesIO()

        print(f"提出処理を開始します: {len(selected_images)}枚")

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for idx, img_info in enumerate(tqdm(selected_images, desc="Upscaling & Packaging")):
                try:
                    result = self._process_single_image(idx, img_info, submission_prefix, s3)
                    if result:
                        csv_data.append(result['csv_entry'])
                        processed_file_paths.append(result['rel_path'])
                        
                        # アップスケール画像をZIPに追加
                        # S3からダウンロードしてZIPへ
                        upscaled_key = result['upscaled_key']
                        upscaled_filename = result['upscaled_filename']
                        
                        print(f"Adding to ZIP: {upscaled_key}")
                        img_bytes = s3.download_file(upscaled_key)
                        zip_file.writestr(upscaled_filename, img_bytes)

                except Exception as e: # pylint: disable=broad-exception-caught
                    print(f"Error processing {img_info.get('path')}: {e}")

            # 4. CSV作成とZIPへの追加
            if csv_data:
                # submit.csv作成
                df = pd.DataFrame(csv_data)
                # Adobe Stock用フォーマットへ
                submit_df = df.rename(columns={
                    'upscaled_filename': 'Filename',
                    'title': 'Title',
                    'tags': 'Keywords',
                    'category': 'Category'
                })
                # 必要なカラムのみ
                submit_df = submit_df[['Filename', 'Title', 'Keywords', 'Category']]
                
                csv_io = io.StringIO()
                submit_df.to_csv(csv_io, index=False, encoding='utf-8-sig')
                zip_file.writestr("submit.csv", csv_io.getvalue())

        # 5. ステータス更新 (Team A連携)
        if processed_file_paths:
            self.state_mgr.update_status(processed_file_paths, STATUS_REGISTERED)

        print(f"提出バッチ処理完了")
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _process_single_image(
        self,
        idx: int,
        img_info: Dict,
        submission_prefix: str,
        _s3_client
    ) -> Optional[Dict]:
        """
        Process a single image: upscale, generate metadata, and prepare CSV entry.
        """
        input_key = img_info['path'] # S3 Key

        # ファイル名生成
        original_basename = os.path.splitext(os.path.basename(input_key))[0]
        new_filename = f"upscaled_{idx:03d}_{original_basename}.png"
        
        # S3 Output Key
        output_key = f"{submission_prefix}/{new_filename}"

        # 2. アップスケール実行 (S3 -> S3)
        self.processor.upscale_image(input_key, output_key)

        # 3. メタデータ取得
        prompt = img_info.get('prompt', "")
        # プロンプトバックアップロジックはS3化が難しいので簡易的にスキップ
        # 必要ならget_objectでメタデータを取るべきだが今回は省略

        # タグ生成
        stored_tags_str = img_info.get('tags', "")
        stored_tags = (
            [t.strip() for t in stored_tags_str.split(",") if t.strip()]
            if stored_tags_str else []
        )

        meta = self.metadata_mgr.get_image_metadata(prompt, user_tags=stored_tags)

        return {
            "csv_entry": {
                "filename": os.path.basename(input_key),
                "upscaled_filename": new_filename,
                "title": meta.get("title", ""),
                "tags": meta.get("tags", ""),
                "category": meta.get("category", 8),
                "prompt": prompt
            },
            "rel_path": input_key,
            "upscaled_key": output_key,
            "upscaled_filename": new_filename
        }
