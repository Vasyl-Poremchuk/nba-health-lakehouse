import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from pytest_mock import MockerFixture

from nbahl.writers.s3_writer import S3Writer


def test_object_exists_true(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.s3_writer.boto3.Session", return_value=mock_session
    )
    mock_session.client.return_value.head_object.return_value = {}

    s3_writer = S3Writer(bucket="nbahl-bronze-dev")
    result = s3_writer.object_exists(
        key="2025-26/league-game-logs-00-t-regular-season.parquet"
    )

    assert result is True


def test_object_exists_false(mocker: MockerFixture) -> None:
    error_payload = ClientError(
        error_response={"Error": {"Code": "404", "Message": "NoSuchKey"}},
        operation_name="HeadObject",
    )

    mock_session = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.s3_writer.boto3.Session", return_value=mock_session
    )
    mock_session.client.return_value.head_object.side_effect = error_payload

    s3_writer = S3Writer(bucket="nbahl-bronze-dev")
    result = s3_writer.object_exists(
        key="2025-26/league-game-logs-00-t-regular-season.parquet"
    )

    assert result is False


def test_object_exists_raise_client_error(mocker: MockerFixture) -> None:
    error_payload = ClientError(
        error_response={"Error": {"Code": "403", "Message": "Forbidden"}},
        operation_name="HeadObject",
    )

    mock_session = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.s3_writer.boto3.Session", return_value=mock_session
    )
    mock_session.client.return_value.head_object.side_effect = error_payload

    s3_writer = S3Writer(bucket="nbahl-bronze-dev")

    with pytest.raises(ClientError) as exc_info:
        s3_writer.object_exists(
            key="2025-26/league-game-logs-00-t-regular-season.parquet"
        )

    error_response = exc_info.value.response["Error"]

    assert error_response["Code"] == "403"
    assert error_response["Message"] == "Forbidden"


def test_object_exists_raise_unexpected_error(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.s3_writer.boto3.Session", return_value=mock_session
    )
    mock_session.client.return_value.head_object.side_effect = (
        NoCredentialsError()
    )

    s3_writer = S3Writer(bucket="nbahl-bronze-dev")

    with pytest.raises(NoCredentialsError):
        s3_writer.object_exists(
            key="2025-26/league-game-logs-00-t-regular-season.parquet"
        )
