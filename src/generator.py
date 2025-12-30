"""
Image Generator Module.

Interacts with OpenAI API to generate image descriptions, prompts, and images.
"""
import json
import base64
from typing import List, Dict, Optional
import requests
from openai import OpenAI
from src.styles import STYLE_DEFINITIONS

# pylint: disable=broad-exception-caught

class ImageGenerator:
    """
    Class for generating images via OpenAI API.
    """
    def __init__(self, api_key: str, model_name: str = "dall-e-3"):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def generate_image_description(
        self, keyword: str, n_ideas: int = 10, style: str = "japanese_simple"
    ) -> List[str]:
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

        if style in STYLE_DEFINITIONS:
            style_info = STYLE_DEFINITIONS[style]
            style_prompt = style_info.get("idea_prompt", "")
            
            prompt_content = f"""
            以下のテーマの画像{n_ideas}種類を生成するので、それぞれの画像の詳細な説明を日本語で考えてください。
            
            テーマ : {keyword}
            
            ルール : 
            - ロゴ、企業名、ブランド、実在の人物、著作権で保護されたキャラクターは使用禁止。
            - 文字を画像に含めないでください。
            - スタイル : {style_prompt}
            """
        else:
            # フォールバック
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
                tool_choice={
                    "type": "function",
                    "function": {"name": "set_image_descriptions"}
                },
            )

            args = json.loads(
                completion.choices[0].message.tool_calls[0].function.arguments
            )
            return args["descriptions"]
        except Exception as e:
            print(f"説明生成エラー: {e}")
            return []

    def generate_drawing_prompt(
        self, seed_description: str, style: str = "japanese_simple"
    ) -> str:
        """
        日本語のシード説明をDALL-E 3用の詳細な英語プロンプトに変換します。
        """

        # スタイル制約を取得
        # default
        style_constraints = (
            "Minimalist Japanese line art, simple, clean lines. White background. No text."
        )
        if style in STYLE_DEFINITIONS:
            style_constraints = STYLE_DEFINITIONS[style]["drawing_prompt"]

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
        Translate the following image description into a detailed English prompt (~100 words).
        Focus on visual details, style, and composition. Do NOT include instructions like "create an image".
        
        Original Description: {seed_description}
        
        Style constraints: {style_constraints}
        """

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                tools=tools,
                tool_choice={
                    "type": "function",
                    "function": {"name": "set_drawing_prompt"}
                },
            )
            args = json.loads(
                completion.choices[0].message.tool_calls[0].function.arguments
            )
            return args["prompt"]
        except Exception as e:
            print(f"描画プロンプト生成エラー: {e}")
            return ""

    def get_styles(self) -> Dict:
        """利用可能なスタイル定義を返します"""
        return STYLE_DEFINITIONS

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        n: int = 1,
        response_format: Optional[str] = None
    ): # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
        """
        Generate an image using OpenAI API and upload to S3.
        指定されたOpenAIモデルを使用して画像を生成し、S3に保存します。
        output_path: S3 Key (e.g. "output/timestamp_keyword/generated_images/img_001.png")
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

            print(f"Generating image with params: {params}")
            response = self.client.images.generate(**params)

            image_item = response.data[0]

            # 自動判別
            image_content = (
                getattr(image_item, 'url', None) or
                getattr(image_item, 'b64_json', None)
            )
            is_b64 = bool(getattr(image_item, 'b64_json', None))

            img_bytes = None
            if not is_b64:
                # url case
                if image_content:
                    img_bytes = requests.get(image_content, timeout=60).content
            else:
                # b64_json case
                img_bytes = base64.b64decode(image_content)

            if img_bytes:
                # S3にアップロード
                from src.storage import S3Manager
                s3 = S3Manager()
                s3.upload_file(img_bytes, output_path, content_type="image/png")
                print(f"画像をS3に保存しました: {output_path}")
                return output_path
            
            raise ValueError("API returned no recognized image data (url or b64_json)")

        except Exception as e:
            print(f"モデル {self.model_name} での画像生成エラー: {e}")
            raise e
