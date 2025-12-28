import os
import time
import requests
import json
from openai import OpenAI
from typing import List, Dict, Optional

class ImageGenerator:
    def __init__(self, api_key: str, model_name: str = "dall-e-3"):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def generate_image_description(self, keyword: str, n_ideas: int = 10, style: str = "japanese_simple") -> List[str]:
        """
        キーワードに基づいて、異なる画像の説明（シードプロンプト）を生成します。
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_image_descriptions",
                    "description": f"{n_ideas}個の異なる画像説明を生成します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "descriptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "画像説明のリスト。"
                            }
                        },
                        "required": ["descriptions"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        if style == "japanese_simple":
             prompt_content = f"""
            以下のテーマの画像{n_ideas}種類を生成するので、それぞれの画像の詳細な説明を日本語で考えてください。
            
            テーマ : {keyword}
            
            ルール : 
            - ロゴ、企業名、ブランド、実在の人物、著作権で保護されたキャラクターは使用禁止。
            - 文字を画像に含めないでください。
            - スタイル : ミニマルな5色以下のイラスト。シンプルで手描き風のラインアート、清潔感のある線。背景は透過しており、余白（ネガティブスペース）を効果的に活用。日本の現代的なイラストスタイル。
            """
        else:
             prompt_content = f"""
            以下のテーマで魅力的な画像案を{n_ideas}種類、それぞれ詳細に説明してください。
            
            テーマ : {keyword}
            ルール : ロゴや文字、実在の人物は含めないでください。
            """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_content}],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "set_image_descriptions"}},
            )
            
            args = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
            return args["descriptions"]
        except Exception as e:
            print(f"説明生成エラー: {e}")
            return []

    def generate_drawing_prompt(self, seed_description: str) -> str:
        """
        日本語のシード説明をDALL-E 3用の詳細な英語プロンプトに変換します。
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_drawing_prompt",
                    "description": "英語の描画プロンプトを設定します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"}
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

        content = f"""
        Translate the following image description into a detailed English prompt (~100 words) suitable for an AI image generator (DALL-E 3).
        Focus on visual details, style, and composition. Do NOT include instructions like "create an image".
        
        Original Description: {seed_description}
        
        Style constraints: Minimalist Japanese line art, simple, clean lines, maximum 5 colors, ample negative space, faceless characters, modern illustration style. White background. No text.
        """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "set_drawing_prompt"}},
            )
            args = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
            return args["prompt"]
        except Exception as e:
            print(f"描画プロンプト生成エラー: {e}")
            return ""

    def generate_image(self, prompt: str, output_path: str, size: Optional[str] = None, quality: Optional[str] = None, n: int = 1, response_format: Optional[str] = None):
        """
        指定されたOpenAIモデルを使用して画像を生成し、保存します。
        """
        try:
            # パラメータを動的に構築 (NoneのものはAPIに送らない)
            params = {
                "model": self.model_name,
                "prompt": prompt,
                "n": n
            }
            if size:
                params["size"] = size
            if quality:
                params["quality"] = quality
            if response_format:
                params["response_format"] = response_format

            response = self.client.images.generate(**params)
            
            image_item = response.data[0]
            
            # 自動判別
            if getattr(image_item, 'url', None):
                image_content = image_item.url
                is_b64 = False
            elif getattr(image_item, 'b64_json', None):
                image_content = image_item.b64_json
                is_b64 = True
            else:
                raise ValueError("API returned no recognized image data (url or b64_json)")

            if not is_b64:
                img_data = requests.get(image_content).content
                with open(output_path, 'wb') as handler:
                    handler.write(img_data)
            else:
                import base64
                img_data = base64.b64decode(image_content)
                with open(output_path, 'wb') as handler:
                    handler.write(img_data)

            print(f"画像を保存しました: {output_path}")
            return output_path

            
        except Exception as e:
            print(f"モデル {self.model_name} での画像生成エラー: {e}")
            raise e
