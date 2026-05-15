"""Tests for the ARIMA/SARIMA forecasting model."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_enterprise_workflow.forecasting.arima import model

_FIXTURES = Path(__file__).parent / "fixtures" / "data" / "output"


class ModelTest(unittest.TestCase):
    """Integration tests for the full ARIMA/SARIMA pipeline.

    Uses pre-generated fixture CSVs instead of the production data directory
    so the tests run in CI without the 181 MB ``data/input/`` tree.
    Models are trained once per class in ``setUpClass`` and reused.
    """

    _tmpdir: str
    _modeldir: str

    @classmethod
    def setUpClass(cls) -> None:
        """Create temp directories and copy fixture CSVs into the output temp dir."""
        cls._tmpdir = tempfile.mkdtemp()
        cls._modeldir = tempfile.mkdtemp()
        for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
            shutil.copy(str(_FIXTURES / csv_file), cls._tmpdir + "/" + csv_file)

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove all temporary directories created during the test class."""
        shutil.rmtree(cls._tmpdir, ignore_errors=True)
        shutil.rmtree(cls._modeldir, ignore_errors=True)

    def test_01_model_train(self) -> None:
        """Model saves an arima.pickle file after training."""
        # Arrange
        with (
            patch(
                "ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT",
                self._tmpdir + "/",
            ),
            patch(
                "ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS",
                self._modeldir + "/",
            ),
        ):
            # Act
            model("2018-11-20", 30, None)
        # Assert
        assert os.path.exists(self._modeldir + "/arima.pickle")

    def test_02_model_predict(self) -> None:
        """Model returns a dict containing the 'arima' key."""
        # Arrange
        with (
            patch(
                "ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT",
                self._tmpdir + "/",
            ),
            patch(
                "ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS",
                self._modeldir + "/",
            ),
        ):
            # Act
            result = model("2018-11-20", 30, None)
        # Assert
        assert "arima" in result
