# src/styles.py

STYLE_DEFINITIONS = {
    "japanese_simple": {
        "label": "Japanese Simple Line Art",
        "idea_prompt": "ミニマルな5色以下のイラスト。シンプルで手描き風のラインアート、清潔感のある線。余白（ネガティブスペース）を効果的に活用。日本の現代的なイラストスタイル。**背景は必ず透過**",
        "drawing_prompt": "Style constraints: Minimalist Japanese line art, simple, clean lines, maximum 5 colors, ample negative space, faceless characters, modern illustration style. White background. No text."
    },
    "photorealistic": {
        "label": "Photorealistic",
        "idea_prompt": "リアルな写真スタイル。高品質なライティング、詳細なテクスチャ、適切な被写界深度。ストックフォトとして使える実用的な構図。",
        "drawing_prompt": "Style constraints: Photorealistic, high quality, highly detailed, cinematic lighting, 8k resolution, professional photography style, shallow depth of field where appropriate. No text."
    },
    "watercolor": {
        "label": "Soft Watercolor",
        "idea_prompt": "柔らかい水彩画スタイル。パステルカラーを中心とした優しい色使い。滲みや筆のタッチを活かした表現。背景は白または淡い色。",
        "drawing_prompt": "Style constraints: Soft watercolor painting, pastel colors, gentle brush strokes, wet-on-wet technique, artistic, dreamy atmosphere. White background. No text."
    },
    "isometric_3d": {
        "label": "Isometric 3D",
        "idea_prompt": "アイソメトリック（等角投影）の3Dイラスト。クリーンなレンダリング、明るい色使い。技術、ビジネス、物流などのテーマに適したスタイル。",
        "drawing_prompt": "Style constraints: Isometric 3D illustration, clean 3D rendering, bright colors, clay render style or low poly, soft lighting. White background. No text."
    },
    "anime_vibrant": {
        "label": "Vibrant Anime",
        "idea_prompt": "鮮やかなアニメスタイル。はっきりとした輪郭線、高い彩度、ダイナミックな構図。日本の商業アニメのような高品質な塗り。",
        "drawing_prompt": "Style constraints: High quality anime style, vibrant colors, clear outlines, cel shading, dynamic composition, Makoto Shinkai style lighting. No text."
    },
    "None": {
        "label": "None",
        "idea_prompt": "",
        "drawing_prompt": ""
    }
}
