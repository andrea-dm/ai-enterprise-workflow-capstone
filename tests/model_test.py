import os
import unittest

from ai_enterprise_workflow.core.config import DIRECTORY_MODELS
from ai_enterprise_workflow.forecasting.arima import model

_DATA_AVAILABLE = os.path.exists("./data/input/")


@unittest.skipIf(not _DATA_AVAILABLE, "requires ./data/input/ — not present in CI")
class ModelTest(unittest.TestCase):
    def test_01_model_train(self):
        model_file = DIRECTORY_MODELS + "arima.pickle"
        date = "2018-11-20"
        duration = 30
        country = None
        model(date, duration, country)
        assert os.path.exists(model_file)

    def test_02_model_predict(self):
        key = "arima"
        date = "2018-11-20"
        duration = 30
        country = None
        result = model(date, duration, country)
        assert key in result
