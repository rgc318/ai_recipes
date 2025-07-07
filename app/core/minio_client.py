# app/core/minio_client.py
import boto3
from botocore.client import Config
from fastapi import UploadFile
from uuid import uuid4
from app.config.settings import settings

class MinioClient:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def upload_fileobj(self, file: UploadFile, bucket_name: str, folder: str = "images") -> str:
        ext = file.filename.split(".")[-1]
        object_name = f"{folder}/{uuid4().hex}.{ext}"

        self.s3.upload_fileobj(
            file.file,
            Bucket=bucket_name,
            Key=object_name,
            ExtraArgs={"ContentType": file.content_type},
        )

        url = f"{settings.MINIO_PUBLIC_ENDPOINT}/{bucket_name}/{object_name}"
        return url

    def create_bucket_if_not_exists(self, bucket_name: str):
        buckets = [b["Name"] for b in self.s3.list_buckets()["Buckets"]]
        if bucket_name not in buckets:
            self.s3.create_bucket(Bucket=bucket_name)

minio_client = MinioClient()
