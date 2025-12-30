"""
Storage Module.

Handles S3 interactions using boto3.
"""
import os
import io
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# pylint: disable=broad-exception-caught

class S3Manager:
    """
    AWS S3 operations manager.
    Requires AWS credentials in environment variables or .env file.
    """
    def __init__(self):
        load_dotenv()
        self.bucket = os.getenv("S3_BUCKET_NAME")
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region
        )

        if not self.bucket:
            raise ValueError("S3_BUCKET_NAME is not set in environment variables.")

    def upload_file(self, file_obj, key: str, content_type: str = None) -> str:
        """
        Uploads a file-like object or bytes to S3 and returns the S3 Key.
        """
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        # file_objがbytesならBytesIOにラップ
        if isinstance(file_obj, bytes):
            file_obj = io.BytesIO(file_obj)

        try:
            # ensure put pointer at start if it's file-like
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
                
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs=extra_args
            )
            return key
        except ClientError as e:
            print(f"S3 Upload Error: {e}")
            raise e

    def download_file(self, key: str) -> bytes:
        """
        Downloads a file from S3 as bytes.
        """
        try:
            buffer = io.BytesIO()
            self.s3_client.download_fileobj(self.bucket, key, buffer)
            buffer.seek(0)
            return buffer.read()
        except ClientError as e:
            print(f"S3 Download Error: {e}")
            raise e
        except Exception as e:
            print(f"S3 General Error: {e}")
            raise e

    def list_objects(self, prefix: str = "") -> list:
        """
        Lists objects in the bucket with the given prefix.
        Returns a list of dicts: {'Key': str, 'LastModified': datetime, 'Size': int}
        """
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
            
            objects = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'Key': obj['Key'],
                            'LastModified': obj['LastModified'],
                            'Size': obj['Size']
                        })
            return objects
        except ClientError as e:
            print(f"S3 List Error: {e}")
            return []

    def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generates a presigned URL for the S3 object.
        """
        try:
            return self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiration
            )
        except ClientError as e:
            print(f"Presigned URL Error: {e}")
            return ""

    def file_exists(self, key: str) -> bool:
        """Checks if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False
