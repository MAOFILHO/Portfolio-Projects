from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef
from pathlib import Path

import boto3

TRAINING_PREFIX = "training-data"
VALIDATION_PREFIX = "validation-data"
OUTPUT_PREFIX = "output"


class S3Client:
    def __init__(self, bucket: str, session: boto3.Session | None = None) -> None:
        self.bucket = bucket
        self._session = session or boto3.Session()
        self._s3 = self._session.client("s3")

    def upload_training_data(self, scenario_id: str, local_path: Path) -> str:
        key = f"{TRAINING_PREFIX}/{scenario_id}/train.jsonl"
        self._s3.upload_file(str(local_path), self.bucket, key)
        return key

    def upload_validation_data(self, scenario_id: str, local_path: Path) -> str:
        key = f"{VALIDATION_PREFIX}/{scenario_id}/validation.jsonl"
        self._s3.upload_file(str(local_path), self.bucket, key)
        return key

    def list_output_artifacts(self, scenario_id: str) -> list[str]:
        prefix = f"{OUTPUT_PREFIX}/{scenario_id}/"
        keys: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def empty_bucket(self) -> int:
        """Delete every object version and delete marker. Returns count deleted."""
        deleted_count = 0
        paginator = self._s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=self.bucket):
            to_delete = [
                {"Key": v["Key"], "VersionId": v["VersionId"]}
                for v in page.get("Versions", []) + page.get("DeleteMarkers", [])
            ]
            if not to_delete:
                continue
            for i in range(0, len(to_delete), 1000):
                batch = to_delete[i : i + 1000]
                # cast: the batch is built as {"Key", "VersionId"} dicts, which match
                # ObjectIdentifierTypeDef structurally but not nominally.
                self._s3.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": cast("list[ObjectIdentifierTypeDef]", batch)},
                )
                deleted_count += len(batch)
        return deleted_count
