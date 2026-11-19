"""Reads the model registry the trainer writes to (see training/app/registry.py)."""

import io
import json

import boto3
import torch
from botocore.exceptions import ClientError

from app import config

LATEST_KEY = "models/latest.json"


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT,
        aws_access_key_id="recoil",
        aws_secret_access_key="recoil",
        region_name="us-east-1",
    )


def read_latest(s3) -> dict | None:
    """Returns {"version", "key", "auc"} or None if nothing is promoted yet."""
    try:
        response = s3.get_object(Bucket=config.S3_BUCKET, Key=LATEST_KEY)
    except ClientError:
        return None
    return json.loads(response["Body"].read())


def download_checkpoint(s3, key: str) -> dict:
    response = s3.get_object(Bucket=config.S3_BUCKET, Key=key)
    data = response["Body"].read()
    # weights_only=True refuses to unpickle arbitrary Python objects,
    # so a tampered model file can't run code on this server.
    return torch.load(io.BytesIO(data), weights_only=True)
