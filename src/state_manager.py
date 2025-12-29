import os
import json
import glob
from typing import Dict, List, Optional
from datetime import datetime

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
        ファイルシステムをスキャンし、DBに未登録の画像を 'UNPROCESSED' として追加する。
        DBにあってファイルが存在しないエントリは現在は保持する（履歴として残す方針）。
        """
        # outputディレクトリ以下の全pngファイルを探索 (generated_imagesフォルダ内)
        # パターン: output/YYYY-MM-DD_Keyword/generated_images/*.png
        search_pattern = os.path.join(self.base_dir, "**", "generated_images", "*.png")
        found_files = glob.glob(search_pattern, recursive=True)

        updated = False
        for file_path in found_files:
            # 絶対パスを相対パスに変換してキーにする
            rel_path = os.path.relpath(file_path, os.getcwd())
            
            # Windowsのパス区切りを統一 ('/'推奨)
            rel_path = rel_path.replace("\\", "/")

            if rel_path not in self.db:
                # 新規発見ファイル
                prompt, tags, keyword = self._extract_prompt_if_possible(file_path)
                self.db[rel_path] = {
                    "status": STATUS_UNPROCESSED,
                    "added_at": datetime.now().isoformat(),
                    "prompt": prompt,
                    "tags": tags,
                    "keyword": keyword
                }
                updated = True
        
        if updated:
            self.save_db()

    def _extract_prompt_if_possible(self, file_path: str) -> tuple[str, str]:
        """
        prompt.csvがあればそこからプロンプトを読み取る（簡易実装）
        """
        try:
            dir_path = os.path.dirname(file_path)
            csv_path = os.path.join(dir_path, "prompt.csv")
            if os.path.exists(csv_path):
                # ファイル名を取得
                filename = os.path.basename(file_path)
                import pandas as pd
                df = pd.read_csv(csv_path)
                # filenameカラムで検索
                row = df[df['filename'] == filename]
                if not row.empty:
                    # keywordカラムがあれば取得、なければ空文字
                    keyword = row.iloc[0].get('keyword', "")
                    # NaNの場合は空文字にする
                    if pd.isna(keyword):
                        keyword = ""
                    return row.iloc[0]['prompt'], row.iloc[0].get('tags', ""), keyword
        except Exception:
            pass
        return "", "", ""

    def get_images_by_status(self, status: str) -> List[Dict]:
        """指定したステータスの画像リストを返す"""
        result = []
        for path, data in self.db.items():
            if data["status"] == status:
                # ファイルが存在するか確認（物理削除済みは返さない方が安全）
                if os.path.exists(path):
                    item = data.copy()
                    item["path"] = path
                    result.append(item)
        
        # added_atの降順（新しい順）にソート
        result.sort(key=lambda x: x.get("added_at", ""), reverse=True)
        return result

    def get_unprocessed_images(self) -> List[Dict]:
        """未処理画像一覧を返す"""
        return self.get_images_by_status(STATUS_UNPROCESSED)

    def update_status(self, file_paths: List[str], new_status: str):
        """
        指定された画像のステータスを更新する
        """
        updated = False
        for path in file_paths:
            # パス区切りの統一
            rel_path = path.replace("\\", "/")
            
            # DBにキーがあるか確認（相対パスで管理しているため）
            # 入力がフルパスかもしれないので、relpath変換を試みる
            if os.path.isabs(path):
                rel_path = os.path.relpath(path, os.getcwd()).replace("\\", "/")

            if rel_path in self.db:
                self.db[rel_path]["status"] = new_status
                self.db[rel_path]["updated_at"] = datetime.now().isoformat()
                updated = True
            else:
                print(f"Warning: Image not found in DB: {path}")

        if updated:
            self.save_db()

if __name__ == "__main__":
    # 簡易動作確認
    mgr = StateManager()
    print(f"DB Path: {mgr.db_path}")
    unprocessed = mgr.get_unprocessed_images()
    print(f"Unprocessed Images: {len(unprocessed)}")
    # for img in unprocessed[:3]:
    #     print(img)
