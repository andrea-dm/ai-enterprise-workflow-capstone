"""Tests for the ARIMA/SARIMA forecasting model (forecasting.arima)."""

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_enterprise_workflow.forecasting.arima import model

_FIXTURES = Path(__file__).parent.parent / "resources" / "forecasting"
_OUTPUT_TARGET = "ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT"
_MODELS_TARGET = "ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS"

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Non-stationary starting autoregressive parameters:UserWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:Too few observations to estimate starting parameters:UserWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:Maximum Likelihood optimization failed to converge"
    ),
]


@pytest.fixture(scope="class")
def arima_dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    """Create isolated output and model directories with fixture CSVs pre-copied.

    Args:
        tmp_path_factory: Pytest built-in factory for class-scoped temporary paths.

    Returns:
        A 2-tuple of ``(output_dir, model_dir)``, each ending with ``'/'``.
    """
    output_dir = tmp_path_factory.mktemp("arima_output")
    model_dir = tmp_path_factory.mktemp("arima_models")
    for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
        shutil.copy(str(_FIXTURES / csv_file), str(output_dir / csv_file))
    return str(output_dir) + "/", str(model_dir) + "/"


class TestArima:
    """Test suite for forecasting.arima public API."""

    @pytest.mark.integration
    @pytest.mark.slow
    class TestIntegration:
        """Real model-fitting tests executed against the pre-built fixture CSVs.

        Both tests share the same ``arima_dirs`` fixture (class-scoped): the first
        test trains and serialises the models; the second test exercises the
        load-from-cache path.
        """

        def test_model_train_saves_arima_and_sarima_pickles(
            self, arima_dirs: tuple[str, str]
        ) -> None:
            """model() persists both arima.pickle and sarima.pickle on first run."""
            output_dir, model_dir = arima_dirs
            with (
                patch(_OUTPUT_TARGET, output_dir),
                patch(_MODELS_TARGET, model_dir),
            ):
                model("2018-11-20", 30, None)
            assert os.path.exists(model_dir + "arima.pickle")
            assert os.path.exists(model_dir + "sarima.pickle")

        def test_model_predict_returns_arima_and_sarima_keys(
            self, arima_dirs: tuple[str, str]
        ) -> None:
            """model() returns a dict containing both 'arima' and 'sarima' keys."""
            output_dir, model_dir = arima_dirs
            with (
                patch(_OUTPUT_TARGET, output_dir),
                patch(_MODELS_TARGET, model_dir),
            ):
                result = model("2018-11-20", 30, None)
            assert "arima" in result
            assert "sarima" in result
