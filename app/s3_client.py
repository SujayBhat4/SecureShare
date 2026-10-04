from urllib.parse import quote

import boto3
from botocore.config import Config

from app.config import settings

# One S3 client for the whole app. boto3 finds the AWS access key and secret in the
# environment by itself, so they are never passed around in our code.
# The regional endpoint is set on purpose: without it the presigned URLs point to the
# global S3 address and S3 answers "307 redirect", which breaks the signature.
s3 = boto3.client(
    "s3",
    region_name=settings.aws_region,
    endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)


# Stores the file bytes in the private bucket under the given (random) key
def upload_file(key: str, data: bytes, content_type: str) -> None:
    s3.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=data, ContentType=content_type)


# Removes the file from the bucket
def delete_file(key: str) -> None:
    s3.delete_object(Bucket=settings.s3_bucket_name, Key=key)


# Makes a temporary (60 second) S3 URL for one file. "inline" opens it in the
# browser, "attachment" saves it with its real name. The bucket stays private:
# this URL is the only way to read the file, and it dies quickly.
def presigned_url(key: str, content_type: str, original_name: str, as_attachment: bool) -> str:
    if as_attachment:
        # filename= is a plain fallback; filename*= carries the real name for any language
        ascii_name = original_name.encode("ascii", "ignore").decode().replace('"', "")
        disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(original_name)}"
    else:
        disposition = "inline"

    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": key,
            "ResponseContentDisposition": disposition,
            "ResponseContentType": content_type,
        },
        ExpiresIn=settings.presigned_url_seconds,
    )
