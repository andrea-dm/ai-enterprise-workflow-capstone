"""Tests for the stdlib-based event logger (core.log_events)."""

import json
import logging
import string
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from ai_enterprise_workflow.core.log_events import (
    PACKAGE_LOGGER_NAME,
    get_logger,
    log_ingest,
    log_predict,
    log_train,
    setup_logging,
)


class TestLogEvents:
    """Test suite for core.log_events public functions."""

    @pytest.mark.unit
    class TestUnit:
        """Happy-path and validation tests."""

        def test_get_logger_returns_child_of_package_logger(self) -> None:
            """get_logger returns a logger namespaced under the package root."""
            logger = get_logger("some.module")
            assert logger.name.startswith(PACKAGE_LOGGER_NAME)

        def test_get_logger_already_namespaced_returns_same(self) -> None:
            """get_logger with a fully-qualified name returns it unchanged."""
            logger = get_logger("ai_enterprise_workflow.forecasting.arima")
            assert logger.name == "ai_enterprise_workflow.forecasting.arima"

        def test_log_ingest_emits_info_record(
            self, caplog: pytest.LogCaptureFixture
        ) -> None:
            """log_ingest emits an INFO record with event='ingest'."""
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_ingest((1000, 10))
            assert any(
                r.getMessage() == "ingest event"
                and getattr(r, "event", None) == "ingest"
                for r in caplog.records
            )

        def test_log_train_emits_info_record(
            self, caplog: pytest.LogCaptureFixture
        ) -> None:
            """log_train emits an INFO record with event='train' and model field."""
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_train("arima", (500, 1), {"mse": 0.05})
            assert any(
                getattr(r, "event", None) == "train"
                and getattr(r, "model", None) == "arima"
                for r in caplog.records
            )

        def test_log_predict_emits_info_record(
            self, caplog: pytest.LogCaptureFixture
        ) -> None:
            """log_predict emits an INFO record with event='predict'."""
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_predict("sarima", {"date": "2020-01-01"}, {"revenue": 1000.0})
            assert any(
                getattr(r, "event", None) == "predict"
                and getattr(r, "model", None) == "sarima"
                for r in caplog.records
            )

        def test_log_ingest_shape_stored_in_record(
            self, caplog: pytest.LogCaptureFixture
        ) -> None:
            """log_ingest stores shape as a list in the record's extra fields."""
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_ingest((42, 7))
            record = next(
                r for r in caplog.records if getattr(r, "event", None) == "ingest"
            )
            assert getattr(record, "shape", None) == [42, 7]

        def test_setup_logging_writes_jsonl_file(self, tmp_path: Path) -> None:
            """setup_logging + log_ingest creates events.jsonl with valid JSON."""
            setup_logging(log_dir=tmp_path)
            log_ingest((100, 5))
            jsonl_file = tmp_path / "events.jsonl"
            assert jsonl_file.exists()
            with jsonl_file.open() as fh:
                lines = [ln.strip() for ln in fh if ln.strip()]
            assert len(lines) >= 1
            record = json.loads(lines[-1])
            assert record.get("event") == "ingest"
            assert "timestamp" in record
            # Reset handlers to avoid polluting subsequent tests
            setup_logging()

    @pytest.mark.contract
    class TestContracts:
        """Property-based invariant tests for core.log_events functions."""

        @given(
            n=st.integers(min_value=1, max_value=5),
            shape=st.tuples(
                st.integers(min_value=1, max_value=10_000),
                st.integers(min_value=1, max_value=100),
            ),
        )
        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_log_ingest_record_count_invariant(
            self, n: int, shape: tuple[int, int], caplog: pytest.LogCaptureFixture
        ) -> None:
            """For any n ≥ 1 calls, exactly n 'ingest' records are emitted."""
            caplog.clear()
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                for _ in range(n):
                    log_ingest(shape)
            ingest_records = [
                r for r in caplog.records if getattr(r, "event", None) == "ingest"
            ]
            assert len(ingest_records) == n

        @given(
            model_name=st.text(
                min_size=1,
                max_size=50,
                alphabet=string.ascii_letters + string.digits,
            )
        )
        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_log_train_any_model_name_emits_record(
            self, model_name: str, caplog: pytest.LogCaptureFixture
        ) -> None:
            """log_train emits a record for any non-empty alphanumeric model name."""
            caplog.clear()
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_train(model_name, (1, 1), {})
            assert any(
                getattr(r, "event", None) == "train"
                and getattr(r, "model", None) == model_name
                for r in caplog.records
            )

        @given(
            query=st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
                st.integers(),
                max_size=3,
            ),
            prediction=st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
                st.floats(allow_nan=False, allow_infinity=False),
                max_size=3,
            ),
        )
        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
        def test_log_predict_any_mapping_emits_record(
            self,
            query: dict[str, int],
            prediction: dict[str, float],
            caplog: pytest.LogCaptureFixture,
        ) -> None:
            """log_predict emits a record for any valid query and
            prediction mappings."""
            caplog.clear()
            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
                log_predict("model", query, prediction)
            assert any(getattr(r, "event", None) == "predict" for r in caplog.records)
