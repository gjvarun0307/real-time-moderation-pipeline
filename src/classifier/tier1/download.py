"""Fetching one versioned Tier 1 model export from R2 at service startup.
"""

import sys
from pathlib import Path

import boto3

R2_BUCKET = "moderation-pipeline"
R2_ACCOUNT_ID = "987b06fd7083dcd8e6e210c4afdedf53"
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = "3c1b25cb63cc6454ec12dc93c8222185"


def fetch_model_artifacts(version_tag: str, dest_dir: Path, secret_access_key: str) -> Path:
    """Downloads model.onnx, tokenizer/, and calibration.json for one version
    tag from R2 into dest_dir/version_tag, skipping files already present."""
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=secret_access_key,
    )

    version_dir = dest_dir / version_tag
    version_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{version_tag}/"

    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix)
        for obj in page.get("Contents", [])
    ]
    if not keys:
        sys.exit(f"no objects found under s3://{R2_BUCKET}/{prefix}")

    for key in keys:
        local_path = version_dir / key[len(prefix) :]
        if local_path.exists():
            continue
        local_path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(R2_BUCKET, key, str(local_path))

    return version_dir
