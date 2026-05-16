"""Tests for the Flask REST API endpoints (service.api)."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from flask.testing import FlaskClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.service.api import app

_MODEL_TARGET = "ai_enterprise_workflow.service.api.model"
_READ_LOG_TARGET = "ai_enterprise_workflow.service.api._read_log_events"


@pytest.fixture
def flask_client() -> Generator[FlaskClient, None, None]:
    """Yield a Flask test client with TESTING mode enabled.

    Yields:
        FlaskClient: a configured Flask test client with ``TESTING=True``.

    Notes:
        Sets ``app.config["TESTING"]`` to ``True``, which enables Werkzeug
        error propagation and disables the error handler during testing.
    """
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestApi:
    """Test suite for service.api /healthz, /predict, and /logs endpoints."""

    @pytest.mark.unit
    class TestUnit:
        """Happy-path and error-path tests for all API routes."""

        def test_readyz_returns_ready_when_csv_exists(
            self,
            flask_client: FlaskClient,
            tmp_path: Path,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """GET /readyz returns 200 when the sentinel CSV exists."""
            (tmp_path / "4 revenue_total.csv").touch()
            monkeypatch.setattr(cfg, "directory_output", tmp_path)
            response = flask_client.get("/readyz")
            assert response.status_code == 200
            assert response.get_json() == {"status": "ready"}

        def test_readyz_returns_503_when_csv_absent(
            self,
            flask_client: FlaskClient,
            tmp_path: Path,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """GET /readyz returns 503 when the sentinel CSV is absent."""
            monkeypatch.setattr(cfg, "directory_output", tmp_path)
            response = flask_client.get("/readyz")
            assert response.status_code == 503
            assert response.get_json() == {
                "status": "not ready",
                "reason": "data not ingested",
            }

        def test_predict_invalid_date_returns_422(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict with non-ISO date returns HTTP 422."""
            response = flask_client.post("/predict?date=not-a-date")
            assert response.status_code == 422
            assert "error" in response.get_json()

        def test_predict_non_positive_duration_returns_422(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict with duration=0 returns HTTP 422."""
            response = flask_client.post("/predict?date=2019-01-01&duration=0")
            assert response.status_code == 422
            assert response.get_json() == {
                "error": "duration must be a positive integer."
            }

        def test_predict_non_integer_duration_returns_422(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict with non-integer duration returns HTTP 422."""
            response = flask_client.post("/predict?date=2019-01-01&duration=abc")
            assert response.status_code == 422
            assert response.get_json() == {
                "error": "duration must be a positive integer."
            }

        def test_predict_with_country_returns_data_key(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict with country returns JSON with 'data' key."""
            # Arrange
            mock_result = {"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}
            with patch(_MODEL_TARGET, return_value=mock_result):
                # Act
                response = flask_client.post(
                    "/predict?date=2018-11-20&duration=30&country=Australia"
                )
            # Assert
            assert "data" in response.get_json()
            assert "drift_warning" in response.get_json()

        def test_predict_without_country_returns_data_key(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict without country returns JSON with 'data' key."""
            # Arrange
            mock_result = {"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}
            with patch(_MODEL_TARGET, return_value=mock_result):
                # Act
                response = flask_client.post("/predict?date=2018-11-20&duration=30")
            # Assert
            assert "data" in response.get_json()

        def test_predict_missing_date_returns_error_string(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /predict without date returns HTTP 400 with JSON error body."""
            # Act
            response = flask_client.post("/predict")
            # Assert
            assert response.status_code == 400
            assert response.get_json() == {"error": "No date parameter was provided."}

        def test_logs_valid_type_returns_data_key(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /logs with valid type returns JSON with 'data' key."""
            # Arrange
            with patch(_READ_LOG_TARGET, return_value=[{"event": "predict"}]):
                # Act
                response = flask_client.post("/logs?type=predict")
            # Assert
            assert "data" in response.get_json()

        def test_logs_missing_type_returns_error_string(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /logs without type returns HTTP 400 with JSON error body."""
            # Act
            response = flask_client.post("/logs")
            # Assert
            assert response.status_code == 400
            assert response.get_json() == {"error": "No type parameter was provided."}

        def test_logs_invalid_type_returns_error_string(
            self, flask_client: FlaskClient
        ) -> None:
            """POST /logs with unknown type returns HTTP 422 with JSON error body."""
            # Act
            response = flask_client.post("/logs?type=unknown")
            # Assert
            assert response.status_code == 422
            assert response.get_json() == {
                "error": "Invalid type parameter was provided."
            }

        def test_healthz_returns_ok(self, flask_client: FlaskClient) -> None:
            """GET /healthz returns HTTP 200 with JSON body ``{"status": "ok"}``."""
            # Act
            response = flask_client.get("/healthz")
            # Assert
            assert response.status_code == 200
            assert response.get_json() == {"status": "ok"}

    @pytest.mark.contract
    class TestContracts:
        """Property-based invariant tests via Hypothesis."""

        @given(duration=st.integers(min_value=1, max_value=365))
        @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_predict_any_valid_duration_returns_data_key(
            self, flask_client: FlaskClient, duration: int
        ) -> None:
            """POST /predict with any duration in [1, 365] returns 'data' key."""
            # Arrange
            mock_result = {"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}
            with patch(_MODEL_TARGET, return_value=mock_result):
                # Act
                response = flask_client.post(
                    f"/predict?date=2018-11-20&duration={duration}"
                )
            # Assert
            assert "data" in response.get_json()

        @given(log_type=st.sampled_from(["ingest", "train", "predict"]))
        @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_logs_all_valid_types_return_data_key(
            self, flask_client: FlaskClient, log_type: str
        ) -> None:
            """POST /logs returns JSON with 'data' key for every registered log type."""
            # Arrange
            with patch(_READ_LOG_TARGET, return_value=[]):
                # Act
                response = flask_client.post(f"/logs?type={log_type}")
            # Assert
            assert "data" in response.get_json()
