"""Tests for the CSV-file event logger (core.logging)."""

import csv
import os
import shutil
import string
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_enterprise_workflow.core.logging import log_ingest, log_predict, log_train

_LOG_TARGET = "ai_enterprise_workflow.core.logging.DIRECTORY_LOGS"


class TestLogging:
    """Test suite for core.logging public functions."""

    @pytest.mark.unit
    class TestUnit:
        """Happy-path and validation tests for log_ingest, log_train, log_predict."""

        def test_log_ingest_creates_file(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """log_ingest creates ingest.csv in the configured log directory."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_ingest((1000, 10))
            assert (tmp_path / "ingest.csv").exists()

        def test_log_train_creates_file(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """log_train creates train.csv in the configured log directory."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_train("test", (1000, 10), {"metric": 0.5})
            assert (tmp_path / "train.csv").exists()

        def test_log_predict_creates_file(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """log_predict creates predict.csv in the configured log directory."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_predict("test", {"date": "2020-01-01"}, {"label": 1})
            assert (tmp_path / "predict.csv").exists()

        def test_log_ingest_header_row(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """First row of ingest.csv contains the canonical column headers."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_ingest((100, 5))
            with open(tmp_path / "ingest.csv") as fh:
                headers = next(csv.reader(fh))
            assert headers == ["id", "time", "shape"]

        def test_log_train_header_row(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """First row of train.csv contains the canonical column headers."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_train("m", (1, 1), {})
            with open(tmp_path / "train.csv") as fh:
                headers = next(csv.reader(fh))
            assert headers == ["id", "time", "version", "model", "shape", "performance"]

        def test_log_predict_header_row(
            self, tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """First row of predict.csv contains the canonical column headers."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_predict("m", {}, {})
            with open(tmp_path / "predict.csv") as fh:
                headers = next(csv.reader(fh))
            assert headers == ["id", "time", "version", "model", "query", "prediction"]

        def test_log_ingest_appends_no_duplicate_header(
            self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
        ) -> None:
            """Two consecutive calls produce exactly 1 header row and 2 data rows."""
            monkeypatch.setattr(_LOG_TARGET, str(tmp_path) + "/")
            log_ingest((10, 2))
            log_ingest((20, 3))
            with open(tmp_path / "ingest.csv") as fh:
                rows = list(csv.reader(fh))
            assert len(rows) == 3
            assert rows[0] == ["id", "time", "shape"]

    @pytest.mark.contract
    class TestContracts:
        """Property-based invariant tests for core.logging functions."""

        @given(
            n=st.integers(min_value=1, max_value=5),
            shape=st.tuples(
                st.integers(min_value=1, max_value=10_000),
                st.integers(min_value=1, max_value=100),
            ),
        )
        def test_log_ingest_row_count_invariant(
            self, n: int, shape: tuple[int, int]
        ) -> None:
            """For any n ≥ 1 and valid shape, ingest.csv has exactly n + 1 lines."""
            directory = tempfile.mkdtemp()
            try:
                with patch(_LOG_TARGET, directory + "/"):
                    for _ in range(n):
                        log_ingest(shape)
                with open(os.path.join(directory, "ingest.csv")) as fh:
                    row_count = sum(1 for _ in fh)
                assert row_count == n + 1
            finally:
                shutil.rmtree(directory, ignore_errors=True)

        @given(
            model_name=st.text(
                min_size=1,
                max_size=50,
                alphabet=string.ascii_letters + string.digits,
            )
        )
        def test_log_train_any_model_name_creates_file(self, model_name: str) -> None:
            """log_train creates train.csv for any non-empty alphanumeric model
            identifier."""
            directory = tempfile.mkdtemp()
            try:
                with patch(_LOG_TARGET, directory + "/"):
                    log_train(model_name, (1, 1), {})
                assert os.path.exists(os.path.join(directory, "train.csv"))
            finally:
                shutil.rmtree(directory, ignore_errors=True)

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
        def test_log_predict_any_mapping_creates_file(
            self, query: dict[str, int], prediction: dict[str, float]
        ) -> None:
            """log_predict creates predict.csv for any valid query and prediction
            mappings."""
            directory = tempfile.mkdtemp()
            try:
                with patch(_LOG_TARGET, directory + "/"):
                    log_predict("model", query, prediction)
                assert os.path.exists(os.path.join(directory, "predict.csv"))
            finally:
                shutil.rmtree(directory, ignore_errors=True)
