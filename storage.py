# storage.py
import boto3
import time
from tempfile import SpooledTemporaryFile
from botocore.exceptions import BotoCoreError, ClientError
import logging

logger = logging.getLogger(__name__)

AWS_ACCESS_KEY = "AKIAU6GD2ASBDQBT4G6T"
AWS_SECRET_KEY = "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"
REGION_NAME = "us-east-1"
BUCKET_NAME = "national-health"


s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME
)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME
)

def generate_s3_key(user_id: str) -> str:
    timestamp = int(time.time())
    return f"uploads/{user_id}/{timestamp}.jpg"

def upload_to_s3_sync(file_data, s3_key: str) -> str:
    try:
        s3.upload_fileobj(
            file_data, BUCKET_NAME, s3_key,
            ExtraArgs={"ContentType": "image/png"}
        )
        return f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{s3_key}"
    except (BotoCoreError, ClientError) as e:
        logger.error(f"S3 upload failed: {str(e)}")
        return None

import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor()

async def upload_to_s3(file_data, s3_key: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, upload_to_s3_sync, file_data, s3_key)
