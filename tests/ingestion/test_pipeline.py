"""Unit tests for ingestion.pipeline public API."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.ingestion.pipeline import clean_data, get_data, prepare_data

_SAMPLE_ROW: dict[str, object] = {
    "invoice": "1a",
    "customer_id": 10,
    "stream_id": "3c",
    "price": 1.0,
    "times_viewed": 1,
    "country": "UK",
    "year": 2019,
    "month": 1,
    "day": 1,
}

_CLEANED_ROW: dict[str, object] = {
    "invoice_id": 1,
    "customer_id": 10,
    "stream_id": 3,
    "price": 1.0,
    "view_count": 1,
    "country": "UK",
    "year": 2019,
    "month": 1,
    "day": 1,
}


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows))


class TestPipeline:
    @pytest.mark.unit
    def test_get_data_reads_valid_json_files(self, tmp_path: Path) -> None:
        """Parses valid JSON input and returns a non-empty DataFrame."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        _write_json(input_dir / "invoices.json", [_SAMPLE_ROW])
        result = get_data(cfg.KEYS, cfg.KEY_NAMES, input_dir, output_dir)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @pytest.mark.unit
    def test_get_data_missing_directory_raises(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError when the input directory does not exist."""
        with pytest.raises(FileNotFoundError):
            get_data(cfg.KEYS, cfg.KEY_NAMES, tmp_path / "nonexistent", tmp_path)

    @pytest.mark.unit
    def test_get_data_malformed_json_raises(self, tmp_path: Path) -> None:
        """Raises ValueError when a JSON file contains invalid content."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (input_dir / "bad.json").write_text("not-valid-json")
        with pytest.raises(ValueError, match=r"."):
            get_data(cfg.KEYS, cfg.KEY_NAMES, input_dir, output_dir)

    @pytest.mark.unit
    def test_clean_data_fills_nulls(self, tmp_path: Path) -> None:
        """Replaces null values so the resulting DataFrame has no missing values."""
        data = pd.DataFrame(
            [
                {
                    "invoice_id": "1a",
                    "customer_id": None,
                    "stream_id": "3c",
                    "price": 1.0,
                    "view_count": 1,
                    "country": "UK",
                    "year": 2019,
                    "month": 1,
                    "day": 1,
                }
            ]
        )
        result = clean_data(data, cfg.KEYS, cfg.KEY_TYPES, tmp_path)
        assert result.isnull().sum().sum() == 0

    @pytest.mark.unit
    def test_clean_data_casts_price_to_float(self, tmp_path: Path) -> None:
        """Coerces the price column to float dtype."""
        data = pd.DataFrame(
            [
                {
                    "invoice_id": "1a",
                    "customer_id": 10,
                    "stream_id": "3c",
                    "price": "1.0",
                    "view_count": 1,
                    "country": "UK",
                    "year": 2019,
                    "month": 1,
                    "day": 1,
                }
            ]
        )
        result = clean_data(data, cfg.KEYS, cfg.KEY_TYPES, tmp_path)
        assert result["price"].dtype == float

    @pytest.mark.unit
    def test_prepare_data_adds_date_column(self, tmp_path: Path) -> None:
        """Adds a 'date' column derived from year/month/day fields."""
        data = pd.DataFrame([_CLEANED_ROW])
        result = prepare_data(data, tmp_path)
        assert "date" in result.columns

    @pytest.mark.unit
    def test_prepare_data_removes_non_positive_prices(self, tmp_path: Path) -> None:
        """Drops rows with non-positive price values."""
        rows: list[dict[str, object]] = [
            {**_CLEANED_ROW, "price": 1.0},
            {**_CLEANED_ROW, "price": -5.0},
        ]
        data = pd.DataFrame(rows)
        result = prepare_data(data, tmp_path)
        assert (result["price"] > 0).all()

    @pytest.mark.unit
    def test_get_data_returns_nonempty_dataframe(self, tmp_path: Path) -> None:
        """Confirms get_data returns at least one row for multi-record input."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        _write_json(input_dir / "invoices.json", [_SAMPLE_ROW, _SAMPLE_ROW])
        result = get_data(cfg.KEYS, cfg.KEY_NAMES, input_dir, output_dir)
        assert len(result) > 0

    @pytest.mark.contract
    @given(price=st.floats(min_value=0.01, max_value=9999.0, allow_nan=False))
    @settings(
        # Rationale: suppressing HealthCheck.function_scoped_fixture because tmp_path is
        # injected by pytest, not Hypothesis; too_slow prevents CI timeouts.
        max_examples=20,
        suppress_health_check=[
            HealthCheck.too_slow,
            HealthCheck.function_scoped_fixture,
        ],
    )
    def test_get_data_schema_contract(self, tmp_path: Path, price: float) -> None:
        """Output columns include all expected keys for arbitrary valid prices."""
        input_dir = tmp_path / "input"
        input_dir.mkdir(exist_ok=True)
        output_dir = tmp_path / "output"
        output_dir.mkdir(exist_ok=True)
        _write_json(input_dir / "invoices.json", [{**_SAMPLE_ROW, "price": price}])
        result = get_data(cfg.KEYS, cfg.KEY_NAMES, input_dir, output_dir)
        assert set(result.columns) >= set(cfg.KEYS)
