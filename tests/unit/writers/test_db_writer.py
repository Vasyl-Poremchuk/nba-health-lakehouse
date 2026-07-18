from datetime import UTC, datetime

import pytest
from pytest_mock import MockerFixture

from nbahl.common.enums import Status
from nbahl.common.models import IngestionRun
from nbahl.config import Settings
from nbahl.writers.db_writer import DBWriter


def test_write_success(mocker: MockerFixture) -> None:
    mock_connect = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.db_writer.psycopg.connect", return_value=mock_connect
    )

    mock_conn = mock_connect.__enter__.return_value
    mock_cur = mock_conn.cursor.return_value.__enter__.return_value

    mock_cur.fetchone.return_value = (1,)
    db_writer = DBWriter(settings=Settings())

    ingestion_run = IngestionRun(
        s3_key="2025-26/league-game-logs-00-t-regular-season.parquet",
        started_at=datetime.now(tz=UTC),
        status=Status.PENDING,
    )

    run_id = db_writer.write(ingestion_run=ingestion_run)

    assert run_id == 1


def test_write_raise_runtime_error(mocker: MockerFixture) -> None:
    mock_connect = mocker.MagicMock()
    mocker.patch(
        "nbahl.writers.db_writer.psycopg.connect", return_value=mock_connect
    )

    mock_conn = mock_connect.__enter__.return_value
    mock_cur = mock_conn.cursor.return_value.__enter__.return_value

    mock_cur.fetchone.return_value = None
    db_writer = DBWriter(settings=Settings())

    ingestion_run = IngestionRun(
        s3_key="2025-26/league-game-logs-00-t-regular-season.parquet",
        started_at=datetime.now(tz=UTC),
        status=Status.PENDING,
    )

    with pytest.raises(
        RuntimeError, match="INSERT INTO ingestion_runs returned no run_id"
    ):
        db_writer.write(ingestion_run=ingestion_run)
