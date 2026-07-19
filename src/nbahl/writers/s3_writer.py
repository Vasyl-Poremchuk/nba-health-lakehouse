from pathlib import Path

import boto3
import structlog
from botocore.exceptions import ClientError

log = structlog.get_logger()


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
        log.info("Uploaded file to S3", bucket=self.bucket, key=key)

    def object_exists(self, key: str) -> bool:
        """Check whether an object exists in the bucket at the given key.

        Args:
            key: S3 object key to check.

        Returns:
            ``True`` if the object exists, ``False`` if a 404 is returned.

        Raises:
            ClientError: Re-raised for any non-404 error.
        """
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)

            return True
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]

            if error_code == "404":
                log.info(
                    "Object not found",
                    error_code=error_code,
                    bucket=self.bucket,
                    s3_key=key,
                )
                return False

            raise
        except Exception as exc:
            log.error(
                "An unexpected error occurred", error=str(exc), exc_info=True
            )
            raise
