import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from PIL import Image
from tqdm import tqdm as tqdm
import shutil

from openai import OpenAI
from google import genai
from google.genai import types

pd.set_option("display.max_colwidth", 120)


class generate_image_for_as:

    def __init__(self, KEYWORD, TAGWORDS, UPSCALED_SUFFIX="upscaled_",  N_IDEA=10):
        self.KEYWORD = KEYWORD
        self.TAGWORDS = TAGWORDS
        self.TODAY = datetime.today().strftime('%Y-%m-%dT%H-%M')
        self.UPSCALED_SUFFIX = UPSCALED_SUFFIX
        self.N_IDEA = N_IDEA
        
        load_dotenv()
        self.openai_client = OpenAI()
        self.gc_client = genai.Client(
            vertexai=True,
            project="vertexai-2024-12",
            location="us-central1"
        )

    def make_prompt_from_seed(self, image_style:str=None):
        """
        OpenAIのAPIを利用して、特定のテーマについて説明したWebページにありそうな画像の説明を生成。

        Args:
            website_image_content: テーマのwebサイトにありそうな画像を生成させるパターンはTrue

        Returns:
            dict: 生成された画像説明が格納された辞書形式。
                キーは "idea_1", "idea_2", ..., "idea_n" となります。
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_image_desctiption",
                    "description": "画像の説明をそれぞれ300字程度で格納する。それぞれバリエーションを持たせる。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            **{f"idea_{i}": {"type": "string"} for i in range(1, 1+self.N_IDEA)}
                        },
                        "required": [ "idea_"+str(i) for i in range(1, 1+self.N_IDEA)],
                        "additionalProperties": False,
                        "strict" : True,
                    },
                },
            }
        ]
        if image_style == "website_random":
                print("make prompt : "+image_style)
                content  = f"""
                以下のテーマについて説明したWebページにありそうな、画像を{self.N_IDEA}種類、それぞれ300文字程度で説明してください。
                画像の説明は、無地の背景に何かが独立して存在しているようなものが望ましいです。
                画像に書かれている内容のみを詳細に説明してください。
                画像中に文字が出現してはなりません。
                    テーマ : {self.KEYWORD}
                    ルール : ロゴ、企業名、ブランド、実在の人物やキャラクターの名前、著作権で保護された作品やアーティストの名前、スタイルを使用することはできません。
                """
        elif image_style == "japanese_simple":
                print("make prompt : "+image_style)
                content  = f"""
                以下のテーマの画像{self.N_IDEA}種類を生成するので、プロンプトをそれぞれ300文字程度で出力しなさい。
                画像に書かれている内容のみを詳細に説明してください。
                    テーマ : {self.KEYWORD}
                    ルール : ロゴ、企業名、ブランド、実在の人物やキャラクターの名前、著作権で保護された作品やアーティストの名前、スタイルを使用することはできません。
                    スタイル : ミニマルな5色以下のイラスト。シンプルで手描き風のラインアート、清潔感のある線。背景はなく、余白（ネガティブスペース）を効果的に活用。顔の描かれていないキャラクターが落ち着いたポーズをとっている。日本の現代的なイラストスタイル。
                """

        else:
            print("make prompt : ramdom")
            content  = f"""
            以下のテーマで魅力的な画像が{self.N_IDEA}種類あるとして、それぞれ300文字程度で説明してください。
            画像に書かれている内容と、描画のスタイルのみを詳細に説明しなさい。
            それぞれの描画のスタイルは異なるものとします。
                テーマ : {self.KEYWORD}
                ルール : ロゴ、企業名、ブランド、実在の人物やキャラクターの名前、著作権で保護された作品やアーティストの名前、スタイルを使用することはできません。
            """

        completion = self.openai_client.chat.completions.create(
            model="o4-mini",
            messages=[{"role": "user", "content": content}],
            tools=tools,
            tool_choice="required",
            user="test-as-survey"
        )
        out = json.loads(completion.choices[0].message.tool_calls[0].function.arguments)
        df_prompt = pd.DataFrame(out.values(), columns=["prompt"])
        return df_prompt

    def get_generation_prompt_from_seed(self, seed_word:str, style=None):
        """
        指定された日本語プロンプト（seed_word）に基づいて、画像生成のための詳細な英語のプロンプトを作成する。

        Args:
            seed_word (str): テーマとなる日本語のプロンプト。
            style (str): そのプロンプトに追記するイラストのスタイル。

        Returns:
            プロンプトのリスト
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_image_generation_prompts_status_tags",
                    "description": "prompt for image generation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                        "strict" : True,
                    },
                },
            }
        ]

        content  = f"""
        以下のテーマで、{self.KEYWORD}について説明した高クオリティのイラストを生成します。
        そのイラストを生成するためのプロンプトを、約100語の英語で詳細に記述してください。
        プロンプトは画像についての説明のみで、Create等の命令は不要です。
        なお、ルールを守ってプロンプトを作成しなさい。
        テーマ : {seed_word}
        ルール : 実在企業のロゴや企業名を含めてはいけません。
        """

        if style:
            content += "\n イラストのスタイル : " + style

        completion = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": content}
            ],
            tools=tools,
            tool_choice="required",
            user="test-as-survey"
        )
        return json.loads(completion.choices[0].message.tool_calls[0].function.arguments)

    def get_en_prompt(self, df_prompt):
        df_cms_pr =  df_prompt.copy()
        prompt_list = df_cms_pr["prompt"].apply(lambda x :self.get_generation_prompt_from_seed(seed_word=x))
        df_cms_pr = df_cms_pr.assign(
                    generation_prompt = [r["prompt"] for r in prompt_list],
                    )
        return df_cms_pr

    def get_register_tags(self, generation_prompt:str):
        """
        Args:
            seed_word (str): テーマとなる日本語のプロンプト。

        Returns:
            プロンプトのリスト
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_image_meta_data",
                    "description": "set image meta data (title, tag, category).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string",
                                    "description": "a title of almost 10 words, effective keywords that cover the most important elements of image.(Japanese)"},
                            "tags": {"type": "string",
                                    "description": "a list of 30 tags to be registered the image with Adobe Stock (Japanese)"},
                            "category" : {"type": "integer",
                                        "description": "Choose one of the following and answer with the number only:  1	Animals 2	Buildings and Architecture 3	Business 4	Drinks 5	The Environment 6	States of Mind 7	Food 8	Graphic Resources 9	Hobbies and Leisure 10	Industry 11	Landscape 12	Lifestyle 13	People 14	Plants and Flowers 15	Culture and Religion 16	Science 17	Social Issues 18	Sports 19	Technology 20	Transport 21	Travel"}
                        },
                        "required": ["tags", "title", "category"],
                        "additionalProperties": False,
                        "strict" : True,
                    },
                },
            }
        ]

        content  = f"""
    あなたは、Adobe Stockで生計を立てている凄腕のイラストレーターです。
    イラストレーターとしての知識とユーザーの検索動向にも詳しく、タグの設定や販売の知識も豊富です。
    以下のプロンプトで画像を生成した画像をAdobeStockに登録しようと思っています。    
    プロンプト : {generation_prompt}

    このプロンプトで生成した画像について、以下のタスクを実行してください。
    1. タイトル候補の提案: 画像に合うタイトル候補を提案してください。タイトルは20文字以上で、具体的に画像の内容を表すようにしてください。
    2. タグ付け: 画像に合うタグを40個提案してください。タグは、カンマ区切りで記述してください。
    3. カテゴリー分類：画像のカテゴリーを数字で提案してください。

    **追加の指示:**
    * Adobe Stockのガイドラインを遵守してください。

    **例:**
    1. **タイトル候補:**
        * 緑豊かな自然の中で深呼吸をする女性
        * リラックス効果抜群！ヨガを楽しむ女性
        * 朝日に照らされて瞑想する女性
    2. **タグ:** 女性,ヨガ,瞑想,自然,リラックス,健康,ウェルネス,森林,朝日,太陽,光,影,緑,木,葉,青空,雲,静寂,平和,癒し,爽やか,美しい,ライフスタイル,ヘルシー,アウトドア,エクササイズ,ストレッチ,ポーズ,呼吸,精神,集中,マインドフルネス,ボディ,シルエット,一人,若い,美しい,笑顔,幸せ,平和,静か,穏やか,優しい,明るい,希望,癒し,自然美,風景,グリーン

    3. **カテゴリー分類:**
    画像が以下のどのカテゴリーかを判定して数字のみをセットしなさい。
    1. Animals: Content related to animals, insects, or pets — at home or in the wild. 
    2. Buildings and Architecture: Structures like homes, interiors, offices, temples, barns, factories, and shelters. 
    3. Business: People in business settings, offices, business concepts, finance, and money
    4. Drinks: Content related to beer, wine, spirits, and other drinks. 
    5. The Environment: Depictions of nature or the places we work and live. 
    6. States of Mind: Content related to people’s emotions and inner voices. 
    7. Food: Anything focused on food and eating. 
    8. Graphic Resources: Backgrounds, textures, and symbols. 
    9. Hobbies and Leisure: Pastime activities that bring joy and/or rela   xation, such as knitting, building model airplanes, and sailing. 
    10. Industry: Depictions of work and manufacturing, like building cars, forging steel, producing clothing, or producing energy. 
    11. Landscape: Vistas, cities, nature, and other locations. 
    12. Lifestyle: The environments and activities of people at home, work, and play. 
    13. People: People of all ages, ethnicities, cultures, genders, and abilities. 
    14. Plants and Flowers: Close-ups of the natural world. 
    15. Culture and Religion: Depictions of the traditions, beliefs, and cultures of people around the world. 
    16. Science: Content with a focus on the applied, natural, medical, and theoretical sciences. 
    17. Social Issues: Poverty, inequality, politics, violence, and other depictions of social issues. 
    18. Sports: Content focused on sports and fitness, including football, basketball, hunting, yoga, and skiing. 
    19. Technology: Computers, smartphones, virtual reality, and other tools designed to increase productivity. 
    20. Transport: Different types of transportation, including cars, buses, trains, planes, and highway systems. 
    21. Travel: Local and worldwide travel, culture, and lifestyles. 
    """

        completion = self.openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": content}
            ],
            tools=tools,
            tool_choice="required",
            user="test-as-survey"
        )
        return json.loads(completion.choices[0].message.tool_calls[0].function.arguments)

    def get_tag(self, generation_prompt:str):
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # get_register_tags関数を実行
                result = self.get_register_tags(generation_prompt)

                # 結果が期待通りか確認
                if isinstance(result, dict) and set(result.keys()) == {'title', 'tags', 'category'}:
                    return result
                else:
                    raise ValueError("Result keys do not match the expected structure.")
            
            except Exception as e:
                retry_count += 1
                print(f"Attempt {retry_count} failed: {e}")
                time.sleep(1)  # 少し待機してからリトライ

        # リトライ上限を超えた場合の処理
        raise Exception("タグ付けにおいて3回エラーが出ました。プロンプトに誤りはないか、OpenAIへの接続に失敗していないか確認してください。")

    def get_tag_df(self, df_cms_pr):
        register_tag = []
        for generation_prompt in zip(df_cms_pr["generation_prompt"]):
            register_tag.append(self.get_tag(generation_prompt))

        df_cms_pr = df_cms_pr.assign(
            title = [r["title"] for r in register_tag],
            register_tag = [r["tags"] for r in register_tag],
            category = [r["category"] for r in register_tag],
        )

        def strip_default_TAGWORD(tmp_tag:str):
            for a_tag_word in self.TAGWORDS:
                tmp_tag.replace(f"{a_tag_word},", "").replace(f"{a_tag_word}", "").strip(" ") 
            return tmp_tag

        df_cms_pr["fixed_tag"] = [f"{','.join(self.TAGWORDS)}, " + strip_default_TAGWORD(tmp_tag) for tmp_tag in df_cms_pr.register_tag]
        df_cms_pr["filename"] = df_cms_pr.index.astype(str).str.zfill(3) +"_"+ df_cms_pr["title"]+".png"
        df_cms_pr["upscale_filename"] = self.UPSCALED_SUFFIX+df_cms_pr["filename"].apply(lambda x:x[:4])+self.TODAY+".png"
        return df_cms_pr

    def set_output_folder(self):
        folder_path = os.path.join(os.getcwd(), "output",self.TODAY+"_"+self.KEYWORD.replace(" ", "_")[:30])
        # フォルダが存在しない場合は作成
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"{folder_path} フォルダを作成しました。")

        return folder_path

    def generate_image(self, prompt:str, filename, output_folder):
        output_file = os.path.join(output_folder, filename)
        try:
            response1 = self.gc_client.models.generate_image(
                model='imagen-3.0-generate-002',
                # model='imagen-4-0-generate-preview-06-06',
                prompt=prompt,
                config=types.GenerateImageConfig(
                    negative_prompt= "character",
                    number_of_images= 1,
                    aspect_ratio="16:9",
                    include_rai_reason= True,
                    output_mime_type= "image/jpeg",
                    # person_generation = "ALLOW_ADULT",
                )
            )
            response1.generated_images[0].image.save(output_file)
            print(f"画像を保存しました: {output_file}")
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            print(response1)
            
    def generate_all_image(self, df_cms_pr, mode="draw"):
        output_folder = self.set_output_folder()
        df_cms_pr.to_csv(os.path.join(output_folder, "prompt.csv"), encoding="sjis", errors='ignore')

        df_submit = df_cms_pr[["upscale_filename", "title", "fixed_tag", "category"]]
        df_submit.columns = ["Filename", "Title", "Keywords", "Category"]
        df_submit.to_csv(os.path.join(output_folder, "submit.csv"), encoding="utf8")
        
        if mode == "draw":
            for dat in df_cms_pr.iterrows():
                prompt = dat[1]["generation_prompt"]
                filename = dat[1]["filename"]
                start_time = datetime.now()
                try :
                    self.generate_image(prompt, filename, output_folder)
                    
                except Exception as e:
                    print(f"生成中にエラーが発生しました: {e}", prompt, filename,)
                job_time = (datetime.now() - start_time).seconds
                time.sleep(max(45-job_time, 0))
        return output_folder

    # アップスケール済みかを確認する関数
    def is_upscaled_file_exists(self, file_path):
        file_dir, file_name = os.path.split(file_path)
        base_name, ext = os.path.splitext(file_name)
        base_name = base_name[:4]+self.TODAY
        upscaled_file_name = f"{self.UPSCALED_SUFFIX}{base_name}{ext}"
        upscaled_file_path = os.path.join(file_dir, "upscale", upscaled_file_name)
        return os.path.exists(upscaled_file_path) or (base_name[:len(self.UPSCALED_SUFFIX)]==self.UPSCALED_SUFFIX)

    # 画像をアップスケールする関数
    def upscale_image(self, file_path):
        try:
            # 画像を開く
            with Image.open(file_path) as img:
                # 新しいサイズを計算 (2倍に拡大)
                new_size = (img.width * 2, img.height * 2)
                # 画像をアップスケール
                upscaled_img = img.resize(new_size, Image.LANCZOS)
                # 保存先のパスを生成
                file_dir, file_name = os.path.split(file_path)
                file_dir = os.path.join(file_dir, "upscale")
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)
                    print(f"{file_dir} フォルダを作成しました。")
                base_name, ext = os.path.splitext(file_name)
                base_name = base_name[:4]+self.TODAY
                upscaled_file_path = os.path.join(file_dir, f"{self.UPSCALED_SUFFIX}{base_name}{ext}")
                # アップスケールした画像を保存
                upscaled_img.save(upscaled_file_path)
                print(f"アップスケール完了: {upscaled_file_path}")
        except Exception as e:
            print(f"エラー: {file_path} - {e}")

    # アップスケール処理を実行する関数
    def upscale_png_in_folder(self):
        base_folder = self.set_output_folder()
        # フォルダを再帰的に探索
        for root, _, files in os.walk(base_folder):
            for file in files:
                if file.lower().endswith(".png"):  # PNGファイルのみ対象
                    file_path = os.path.join(root, file)
                    if not self.is_upscaled_file_exists(file_path):
                        self.upscale_image(file_path)
        print("すべてのPNG画像のアップスケールが完了しました。")

    # 生成に関わるpythonファイルをコピーしておく関数
    def copy_ext_files(self):
        # コピー元ファイルのパス
        src_note_path = "c:\\Users\\athen\\Desktop\\works\\adobestock\\code\\sketch_seed\\08_detail_use.ipynb"
        src_src_path = "c:\\Users\\athen\\Desktop\\works\\adobestock\\code\\sketch_seed\\util.py"
        # コピー先のディレクトリまたはファイル名を指定
        dst_note_path = os.path.join(self.set_output_folder(), "08_detail_use.ipynb")
        dst_src_path = os.path.join(self.set_output_folder(), "util.py")

        try:
            # ファイルをコピー
            shutil.copy(src_note_path, dst_note_path)
            print(f"ファイルをコピーしました: {src_note_path} -> {dst_note_path}")
            shutil.copy(src_src_path, dst_src_path)
            print(f"ファイルをコピーしました: {src_src_path} -> {dst_src_path}")
        except Exception as e:
            print(f"エラーが発生しました: {e}")

    def auto_gen_and_upscale(self, df_prompt):
        print("Get English prompt")
        df_cms_pr = self.get_en_prompt(df_prompt)
        print("Get tags")
        df_cms_pr_with_tag = self.get_tag_df(df_cms_pr)
        output_folder = self.generate_all_image(df_cms_pr_with_tag, mode="draw")
        self.upscale_png_in_folder()
        self.copy_ext_files()

        self.df_cms_pr = df_cms_pr
        self.df_cms_pr_with_tag = df_cms_pr_with_tag
        self.output_folder = output_folder

        print(f"genration finish : {output_folder}")

        return 1
