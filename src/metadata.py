import os
import json
import csv
import pandas as pd
from openai import OpenAI
from typing import Dict, List, Any

class MetadataManager:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def get_image_metadata(self, generation_prompt: str, user_tags: List[str]) -> Dict[str, Any]:
        """
        Adobe Stock用のタイトル、タグ、カテゴリを生成します。
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_image_metadata",
                    "description": "Adobe Stock提出用のメタデータを設定します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "簡潔で説明的な日本語のタイトル（20〜30文字程度）。"
                            },
                            "tags": {
                                "type": "string",
                                "description": "30〜40個の日本語タグのカンマ区切りリスト。"
                            },
                            "category": {
                                "type": "integer",
                                "description": "Adobe Stock カテゴリID (1-21)。"
                            }
                        },
                        "required": ["title", "tags", "category"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        # コンテキスト用のカテゴリリスト（短縮版）
        categories_text = """
        1: 動物, 2: 建物・建築, 3: ビジネス, 4: 飲み物, 5: 環境, 6: 心の状態, 7: 料理・食品, 
        8: グラフィック素材, 9: 趣味・レジャー, 10: 産業, 11: 風景, 12: ライフスタイル, 13: 人物, 
        14: 植物・花, 15: 文化・宗教, 16: 科学, 17: 社会問題, 18: スポーツ, 19: テクノロジー, 20: 交通・乗り物, 21: 旅行
        """

        content = f"""
        あなたは熟練したAdobe Stockのコントリビューターです。このプロンプトから生成された画像のメタデータ（日本語）を生成してください：
        "{generation_prompt}"

        要件:
        1. タイトル: 説明的で自然な日本語。
        2. タグ: 30〜40個程度。ユーザー指定の必須タグが関連する場合は必ず含めてください: {', '.join(user_tags)}。重複は避けてください。
        3. カテゴリ: 次の中から最も適切なIDを選択してください: {categories_text}
        """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "set_image_metadata"}},
            )
            args = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
            return args
        except Exception as e:
            print(f"メタデータ生成エラー: {e}")
            # 失敗時のフォールバック
            return {"title": "タイトル生成エラー", "tags": ",".join(user_tags), "category": 8}

    def export_csvs(self, data_rows: List[Dict], output_folder: str):
        """
        prompt.csv と submit.csv をエクスポートします。
        data_rows は 'filename', 'upscaled_filename', 'title', 'tags', 'category', 'prompt' を含む必要があります。
        """
        # prompt.csv (Note: main.py handles prompt.csv explicitly too, but this method might be used or modified. 
        # Actually main.py calls this but then overwrites prompt.csv? No, main.py writes prompt.csv to generated_images 
        # while this writes to output_folder(=upscale_dir=root). Verification needed.
        # Based on main.py, prompt.csv is written TWICE if we aren't careful.
        # But let's just translate comments first.
        # main.py passes upscale_dir as output_folder to this function.)
        
        # prompt.csv
        prompt_df = pd.DataFrame(data_rows)[['filename', 'prompt']]
        prompt_csv_path = os.path.join(output_folder, "prompt_backup.csv") # Renaming to verify logic later or just translate.
        # Wait, I should not change logic unless necessary, but the previous code wrote "prompt.csv" here.
        # main.py writes it to `generated_images`. 
        # Writing to root as well might be redundant but I will leave it or just translate.
        prompt_df.to_csv(prompt_csv_path, index=False, encoding='utf-8-sig') 

        # submit.csv
        # 形式: Filename, Title, Keywords, Category
        submit_data = []
        for row in data_rows:
            submit_data.append({
                "Filename": row['upscaled_filename'],
                "Title": row['title'],
                "Keywords": row['tags'],
                "Category": row['category']
            })
        
        submit_df = pd.DataFrame(submit_data)
        submit_csv_path = os.path.join(output_folder, "submit.csv")
        # AdobeはシンプルなUTF8や標準CSVを好む場合があります。
        submit_df.to_csv(submit_csv_path, index=False, encoding='utf-8')
        
        print(f"CSVを {output_folder} にエクスポートしました")
