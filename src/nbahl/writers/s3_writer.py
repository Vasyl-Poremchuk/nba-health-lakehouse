from pathlib import Path

import boto3


class S3Writer:
    """Uploads local files to an S3 bucket using the specified AWS profile.

    Args:
        bucket: S3 bucket name.
        profile_name: AWS named profile; uses the default profile when ``None``.
    """

    def __init__(self, bucket: str, profile_name: str | None = None) -> None:
        self.bucket = bucket
        session = boto3.Session(profile_name=profile_name)
        self._client = session.client("s3")

    def write(self, filepath: Path, key: str) -> None:
        """Upload a local file to S3 at the given object key.

        Args:
            filepath: Local file to upload.
            key: S3 object key (destination path within the bucket).
        """
        self._client.upload_file(
            Filename=filepath.as_posix(),
            Bucket=self.bucket,
            Key=key,
        )
