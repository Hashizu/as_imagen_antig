import os
import cv2
import numpy as np

class ImageProcessor:
    def __init__(self):
        pass

    def upscale_image(self, input_path: str, output_path: str, scale_factor: int = 2):
        """
        OpenCVのLanczos補間を使用して画像を拡大します。
        """
        try:
            # 画像読み込み
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")
            
            # Windowsのパスで非ASCII文字が含まれる場合の対応
            # cv2.imread はWindows上の非ASCIIパスをうまく扱えないため、
            # バイナリとして読み込んでからデコードします。
            img_array = np.fromfile(input_path, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
            
            if img is None:
                raise ValueError(f"画像の読み込みに失敗しました: {input_path}")

            # 新しいサイズを計算
            height, width = img.shape[:2]
            new_height, new_width = height * scale_factor, width * scale_factor

            # アップスケール実行
            upscaled_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)

            # 出力ディレクトリが存在することを確認
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 画像保存
            # imwrite も同様にUnicodeパスの問題があるため imencode を使用
            is_success, buffer = cv2.imencode(".png", upscaled_img)
            if is_success:
                with open(output_path, "wb") as f:
                    f.write(buffer)
                print(f"アップスケール画像を保存しました: {output_path}")
            else:
                 raise ValueError("画像のエンコードに失敗しました")

        except Exception as e:
            print(f"画像 {input_path} のアップスケールエラー: {e}")
            raise e
