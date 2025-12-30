"""
State Manager Module.

Manages the lifecycle and status of generated images (Unprocessed, Registered, Excluded).
"""
import os
import json
from typing import Dict, List
from datetime import datetime
import pandas as pd

STATUS_UNPROCESSED = "UNPROCESSED"
STATUS_REGISTERED = "REGISTERED"
STATUS_EXCLUDED = "EXCLUDED"

class StateManager:
    """
    画像のステータス（未処理、登録済、除外）を管理するクラス。
    データの永続化にはJSONファイルを使用する。
    """
    def __init__(self, db_path: str = "data/image_status.json", base_dir: str = "output"):
        self.db_path = db_path
        self.base_dir = base_dir
        self.db = {} # Key: relative_path, Value: {status, timestamp, meta}
        self.load_db()
        self.scan_and_sync()

    def load_db(self):
        """データベース(JSON)を読み込む"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: {self.db_path} is corrupted. Initializing empty DB.")
                self.db = {}
        else:
            self.db = {}

    def save_db(self):
        """データベース(JSON)を保存する"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, indent=2, ensure_ascii=False)

    def scan_and_sync(self):
        """
        S3をスキャンし、DBに未登録の画像を 'UNPROCESSED' として追加する。
        """
        from src.storage import S3Manager
        try:
            s3 = S3Manager()
            # output/以下の全オブジェクトを取得
            objects = s3.list_objects(prefix="output/") # prefix="output/" is base

            found_keys = []
            updated = False

            for obj in objects:
                key = obj['Key']
                # 対象: generated_imagesフォルダ内のpngファイル
                if "generated_images/" in key and key.endswith(".png"):
                    found_keys.append(key)
                    
                    if key not in self.db:
                         # 新規発見ファイル
                        prompt, tags, keyword = self._extract_prompt_if_possible(key)
                        self.db[key] = {
                            "status": STATUS_UNPROCESSED,
                            "added_at": obj['LastModified'].isoformat(),
                            "prompt": prompt,
                            "tags": tags,
                            "keyword": keyword
                        }
                        updated = True

            if updated:
                self.save_db()
        except Exception as e:
            print(f"S3 Scan Error: {e}")

    def _extract_prompt_if_possible(self, file_key: str) -> tuple[str, str, str]:
        """
        prompt.csvが同じディレクトリにあればそこからプロンプトを読み取る
        Returns: (prompt, tags, keyword)
        """
        try:
            # key: output/xxx/generated_images/img_001.png
            # dir: output/xxx/generated_images
            dir_key = os.path.dirname(file_key).replace("\\", "/") # ensure forward slash
            csv_key = f"{dir_key}/prompt.csv"

            from src.storage import S3Manager
            s3 = S3Manager()
            
            if s3.file_exists(csv_key):
                csv_bytes = s3.download_file(csv_key)
                from io import BytesIO
                df = pd.read_csv(BytesIO(csv_bytes))
                
                filename = os.path.basename(file_key)
                row = df[df['filename'] == filename]
                
                if not row.empty:
                    keyword = row.iloc[0].get('keyword', "")
                    if pd.isna(keyword):
                        keyword = ""
                    return row.iloc[0]['prompt'], row.iloc[0].get('tags', ""), keyword
        except Exception: # pylint: disable=broad-exception-caught
            pass
        return "", "", ""

    def get_images_by_status(self, status: str) -> List[Dict]:
        """指定したステータスの画像リストを返す"""
        result = []
        # S3の存在確認はコストが高いので、DBにあるものは存在するとみなす方針に変更
        # もし厳密にやるなら s3.file_exists(path) だがリスト表示のたびにやるのは重い
        for path, data in self.db.items():
            if data["status"] == status:
                item = data.copy()
                item["path"] = path
                result.append(item)

        # added_atの降順（新しい順）にソート
        result.sort(key=lambda x: x.get("added_at", ""), reverse=True)
        return result

    def update_status(self, file_paths: List[str], new_status: str):
        """
        指定された画像のステータスを更新する
        """
        updated = False
        for path in file_paths:
            # S3 Keyがそのまま渡ってくるはず
            if path in self.db:
                self.db[path]["status"] = new_status
                self.db[path]["updated_at"] = datetime.now().isoformat()
                updated = True
            else:
                print(f"Warning: Image not found in DB: {path}")

        if updated:
            self.save_db()

if __name__ == "__main__":
    # 簡易動作確認
    mgr = StateManager()
    print(f"DB Path: {mgr.db_path}")
    unprocessed = mgr.get_images_by_status(STATUS_UNPROCESSED)
    print(f"Unprocessed Images: {len(unprocessed)}")
    # for img in unprocessed[:3]:
    #     print(img)
