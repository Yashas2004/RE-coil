"""
The model registry: where trained models live and which one is "live".

    s3://models/models/<version>/model.pt   every model we ever trained
    s3://models/models/latest.json          pointer to the PROMOTED one

The model-server (next phase) only ever reads latest.json. So "promoting" a
model is just overwriting one small JSON file. Rolling back = pointing it at
an older version. Nothing gets deleted.
"""

import io
import json

import boto3
import torch
from botocore.exceptions import ClientError

from app import config

LATEST_KEY = "models/latest.json"


def s3_client():
    # SeaweedFS runs without auth locally, so any credentials are accepted.
    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT,
        aws_access_key_id="recoil",
        aws_secret_access_key="recoil",
        region_name="us-east-1",
    )


def ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=config.S3_BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=config.S3_BUCKET)


def save_model(s3, model, user_vocab: dict, version: str, content_dim: int) -> str:
    buffer = io.BytesIO()
    torch.save(
        {
            "state_dict": model.state_dict(),
            "user_vocab": user_vocab,
            "num_users": len(user_vocab) + 1,
            "content_dim": content_dim,
            "version": version,
        },
        buffer,
    )
    key = f"models/{version}/model.pt"
    s3.put_object(Bucket=config.S3_BUCKET, Key=key, Body=buffer.getvalue())
    return key


def get_latest(s3) -> dict | None:
    try:
        response = s3.get_object(Bucket=config.S3_BUCKET, Key=LATEST_KEY)
    except ClientError:
        return None
    return json.loads(response["Body"].read())


def promote(s3, version: str, key: str, auc: float):
    body = json.dumps({"version": version, "key": key, "auc": auc})
    s3.put_object(Bucket=config.S3_BUCKET, Key=LATEST_KEY, Body=body.encode())


def should_promote(new_auc: float, current: dict | None) -> bool:
    if new_auc < config.AUC_GATE:
        return False
    if current is None:
        return True
    return new_auc >= current["auc"] - config.AUC_TOLERANCE


def record_run(db, version, num_samples, auc, promoted, key, started_at, finished_at):
    db.execute(
        """
        INSERT INTO training_runs
            (model_version, num_samples, auc, promoted, artifact_key, started_at, finished_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (version, num_samples, auc, promoted, key, started_at, finished_at),
    )


def last_trained_count(db) -> int:
    row = db.execute(
        "SELECT num_samples FROM training_runs ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return 0
    return row[0]
