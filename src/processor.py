"""
Image Processor Module.

Handles image manipulation tasks such as upscaling using OpenCV.
"""
import cv2
import numpy as np
from src.storage import S3Manager

class ImageProcessor:
    """
    Handles image processing tasks, primarily upscaling using OpenCV.
    """
    def __init__(self):
        self.s3 = S3Manager()

    def upscale_image(self, input_path: str, output_path: str, scale_factor: int = 2): # pylint: disable=too-many-locals
        """
        Upscale an image from S3 by the specified factor and save back to S3.
        S3上の画像をダウンロードし、アップスケール後にS3へアップロードします。
        
        Args:
            input_path (str): S3 Key of the input image.
            output_path (str): S3 Key for the upscaled image.
            scale_factor (int): Factor to scale the image by. Default is 2.
        """
        try:
            # S3Manager is already imported
            s3 = S3Manager()

            # S3からダウンロード
            print(f"Dowloading from S3: {input_path}")
            img_bytes = s3.download_file(input_path)
            
            # メモリ上からデコード
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)

            if img is None:
                raise ValueError(f"画像のデコードに失敗しました: {input_path}")

            # 新しいサイズを計算
            height, width = img.shape[:2]
            new_height, new_width = height * scale_factor, width * scale_factor

            # アップスケール実行
            upscaled_img = cv2.resize(
                img,
                (new_width, new_height),
                interpolation=cv2.INTER_LANCZOS4
            )

            # エンコード (メモリバッファへ)
            is_success, buffer = cv2.imencode(".png", upscaled_img)
            
            if is_success:
                # S3へアップロード
                s3.upload_file(buffer.tobytes(), output_path, content_type="image/png")
                print(f"アップスケール画像をS3に保存しました: {output_path}")
            else:
                raise ValueError("画像のエンコードに失敗しました")

        except Exception as e:
            print(f"画像 {input_path} のアップスケールエラー: {e}")
            raise e
