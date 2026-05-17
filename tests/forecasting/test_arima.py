"""Tests for the ARIMA/SARIMA forecasting model (forecasting.arima)."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

import ai_enterprise_workflow.forecasting.arima as arima_module
from ai_enterprise_workflow.forecasting.arima import (
    get_revenue_country,
    model,
    predict,
    train_arima_model,
    train_sarima_model,
)

_FIXTURES = Path(__file__).parent.parent / "resources" / "forecasting"
_OUTPUT_TARGET = "ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT"
_MODELS_TARGET = "ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS"
_ARIMA_TARGET = "ai_enterprise_workflow.forecasting.arima.ARIMA"
_SARIMAX_TARGET = "ai_enterprise_workflow.forecasting.arima.SARIMAX"
_LOG_TRAIN_TARGET = "ai_enterprise_workflow.forecasting.arima.log_train"
_LOG_PREDICT_TARGET = "ai_enterprise_workflow.forecasting.arima.log_predict"
_LOAD_PICKLE_TARGET = "ai_enterprise_workflow.forecasting.arima.load_pickle"
_RESOLVE_REVENUE_TARGET = "ai_enterprise_workflow.forecasting.arima._resolve_revenue"
_RUN_PREDICTIONS_TARGET = "ai_enterprise_workflow.forecasting.arima._run_predictions"
_LOAD_OR_TRAIN_TARGET = "ai_enterprise_workflow.forecasting.arima._load_or_train"
_PREDICT_TARGET = "ai_enterprise_workflow.forecasting.arima.predict"
_DRIFT_TARGET = "ai_enterprise_workflow.monitoring.drift.get_wasserstein_distance"

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
def arima_dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Create isolated output and model directories with fixture CSVs pre-copied.

    Args:
        tmp_path_factory: Pytest built-in factory for class-scoped temporary paths.

    Returns:
        A 2-tuple of ``(output_dir, model_dir)`` as :class:`~pathlib.Path` objects.
    """
    output_dir = tmp_path_factory.mktemp("arima_output")
    model_dir = tmp_path_factory.mktemp("arima_models")
    for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
        shutil.copy(str(_FIXTURES / csv_file), str(output_dir / csv_file))
    return output_dir, model_dir


@pytest.fixture
def revenue_frame() -> pd.DataFrame:
    """Create a tiny daily revenue frame for fast forecasting unit tests."""
    return pd.DataFrame(
        {
            "date": [
                "2020-01-01",
                "2020-01-02",
                "2020-01-03",
                "2020-01-04",
                "2020-01-05",
                "2020-01-06",
            ],
            "revenue": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        }
    )


class TestArima:
    """Test suite for forecasting.arima public API."""

    @pytest.mark.unit
    class TestUnit:
        """Fast unit tests with mocked model, persistence, and I/O boundaries."""

        def test_get_revenue_country_filters_rows_and_resets_index(self) -> None:
            """get_revenue_country returns only date/revenue rows for one country."""
            revenue = pd.DataFrame(
                {
                    "country": ["UK", "US", "UK"],
                    "date": ["2020-01-01", "2020-01-01", "2020-01-02"],
                    "revenue": [100.0, 200.0, 150.0],
                },
                index=[10, 11, 12],
            )

            result = get_revenue_country(revenue, "UK")

            assert list(result.columns) == ["date", "revenue"]
            assert result.to_dict("records") == [
                {"date": "2020-01-01", "revenue": 100.0},
                {"date": "2020-01-02", "revenue": 150.0},
            ]
            assert list(result.index) == [0, 1]

        def test_train_arima_model_fits_saves_global_pickle_and_logs(self) -> None:
            """train_arima_model delegates fitting, global save, and train logging."""
            data = pd.Series([1.0, 2.0, 3.0], name="revenue")
            fitted_model = MagicMock()
            arima_instance = MagicMock()
            arima_instance.fit.return_value = fitted_model

            with (
                patch(_ARIMA_TARGET, return_value=arima_instance) as arima_class,
                patch(_LOG_TRAIN_TARGET) as log_train,
            ):
                result = train_arima_model(data, (1, 0, 1), Path("models"))

            assert result is fitted_model
            arima_class.assert_called_once_with(data, order=(1, 0, 1))
            arima_instance.fit.assert_called_once_with()
            fitted_model.save.assert_called_once_with(
                str(Path("models") / "arima.pickle")
            )
            log_train.assert_called_once_with("arima", data.shape, {})

        def test_train_arima_model_uses_country_pickle_suffix(self) -> None:
            """train_arima_model includes the country suffix when provided."""
            data = pd.Series([1.0, 2.0, 3.0], name="revenue")
            fitted_model = MagicMock()
            arima_instance = MagicMock()
            arima_instance.fit.return_value = fitted_model

            with (
                patch(_ARIMA_TARGET, return_value=arima_instance),
                patch(_LOG_TRAIN_TARGET),
            ):
                train_arima_model(data, (2, 1, 2), Path("models"), country="Australia")

            fitted_model.save.assert_called_once_with(
                str(Path("models") / "arima_Australia.pickle")
            )

        def test_train_sarima_model_fits_saves_global_pickle_and_logs(self) -> None:
            """train_sarima_model delegates fitting, global save, and train logging."""
            data = pd.Series([1.0, 2.0, 3.0], name="revenue")
            fitted_model = MagicMock()
            sarimax_instance = MagicMock()
            sarimax_instance.fit.return_value = fitted_model

            with (
                patch(_SARIMAX_TARGET, return_value=sarimax_instance) as sarimax_class,
                patch(_LOG_TRAIN_TARGET) as log_train,
            ):
                result = train_sarima_model(
                    data, (1, 0, 1), (0, 1, 1, 30), Path("models")
                )

            assert result is fitted_model
            sarimax_class.assert_called_once_with(
                data,
                order=(1, 0, 1),
                seasonal_order=(0, 1, 1, 30),
            )
            sarimax_instance.fit.assert_called_once_with()
            fitted_model.save.assert_called_once_with(
                str(Path("models") / "sarima.pickle")
            )
            log_train.assert_called_once_with("sarima", data.shape, {})

        def test_train_sarima_model_uses_country_pickle_suffix(self) -> None:
            """train_sarima_model includes the country suffix when provided."""
            data = pd.Series([1.0, 2.0, 3.0], name="revenue")
            fitted_model = MagicMock()
            sarimax_instance = MagicMock()
            sarimax_instance.fit.return_value = fitted_model

            with (
                patch(_SARIMAX_TARGET, return_value=sarimax_instance),
                patch(_LOG_TRAIN_TARGET),
            ):
                train_sarima_model(
                    data,
                    (2, 1, 2),
                    (2, 1, 2, 30),
                    Path("models"),
                    country="Australia",
                )

            fitted_model.save.assert_called_once_with(
                str(Path("models") / "sarima_Australia.pickle")
            )

        def test_predict_delegates_to_model_sums_predictions_and_logs_actual(
            self,
        ) -> None:
            """predict returns model predictions, their sum, and logs actual revenue."""
            forecast_model = MagicMock()
            predictions = pd.Series([10.5, 20.0, 4.5])
            forecast_model.predict.return_value = predictions

            with patch(_LOG_PREDICT_TARGET) as log_predict:
                result_predictions, result_sum = predict(
                    forecast_model,
                    "arima",
                    start=2,
                    end=4,
                    actual=100.0,
                )

            assert result_predictions is predictions
            assert result_sum == pytest.approx(35.0)  # type: ignore[reportUnknownMemberType]
            forecast_model.predict.assert_called_once_with(start=2, end=4, dynamic=True)
            log_predict.assert_called_once_with(
                "arima",
                {"start": 2, "end": 4},
                {"revenue_predicted": predictions.sum(), "revenue_actual": 100.0},
            )

        def test_load_or_train_loads_existing_pickle_without_training(self) -> None:
            """_load_or_train loads an existing pickle and skips training."""
            model_path = MagicMock(spec=Path)
            model_path.exists.return_value = True
            loaded_model = MagicMock()
            train_fn = MagicMock()

            with patch(_LOAD_PICKLE_TARGET, return_value=loaded_model) as load_pickle:
                result = arima_module._load_or_train(model_path, train_fn)

            assert result is loaded_model
            load_pickle.assert_called_once_with(str(model_path))
            train_fn.assert_not_called()

        def test_load_or_train_trains_when_pickle_is_missing(self) -> None:
            """_load_or_train calls the training function when the pickle is missing."""
            model_path = MagicMock(spec=Path)
            model_path.exists.return_value = False
            trained_model = MagicMock()
            train_fn = MagicMock(return_value=trained_model)

            with patch(_LOAD_PICKLE_TARGET) as load_pickle:
                result = arima_module._load_or_train(model_path, train_fn)

            assert result is trained_model
            load_pickle.assert_not_called()
            train_fn.assert_called_once_with()

        def test_model_creates_model_directory_and_delegates_to_prediction_runner(
            self, revenue_frame: pd.DataFrame
        ) -> None:
            """model creates the model directory and delegates to _run_predictions."""
            directory_models = MagicMock(spec=Path)
            output_dir = MagicMock(spec=Path)
            expected = {"arima": 1.0, "sarima": 2.0, "drift": 0.3}

            with (
                patch(_MODELS_TARGET, directory_models),
                patch(_OUTPUT_TARGET, output_dir),
                patch(
                    _RESOLVE_REVENUE_TARGET,
                    return_value=(revenue_frame, "_Australia"),
                ) as resolve_revenue,
                patch(
                    _RUN_PREDICTIONS_TARGET, return_value=expected
                ) as run_predictions,
            ):
                result = model("2020-01-03", duration=2, country="Australia")

            assert result == expected
            directory_models.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            resolve_revenue.assert_called_once_with("Australia", output_dir)
            run_predictions.assert_called_once_with(
                revenue_frame,
                "2020-01-03",
                2,
                directory_models,
                "_Australia",
            )

        def test_run_predictions_uses_mocked_models_writes_predictions_and_scores_drift(
            self, revenue_frame: pd.DataFrame
        ) -> None:
            """_run_predictions uses mocked model, CSV, and drift boundaries."""
            arima_model = MagicMock()
            sarima_model = MagicMock()
            arima_predictions = pd.Series({3: 41.0, 4: 42.0, 5: 43.0})
            sarima_predictions = pd.Series({3: 51.0, 4: 52.0, 5: 53.0})

            with (
                patch(_OUTPUT_TARGET, Path("output")),
                patch(
                    _LOAD_OR_TRAIN_TARGET,
                    side_effect=[arima_model, sarima_model],
                ) as load_or_train,
                patch(
                    _PREDICT_TARGET,
                    side_effect=[
                        (arima_predictions, 111.0),
                        (sarima_predictions, 222.0),
                    ],
                ) as predict_mock,
                patch.object(pd.DataFrame, "to_csv") as to_csv,
                patch(_DRIFT_TARGET, return_value=0.25) as get_wasserstein_distance,
            ):
                result = arima_module._run_predictions(
                    revenue_frame,
                    "2020-01-03",
                    duration=2,
                    directory_models=Path("models"),
                    file_suffix="_Australia",
                )

            assert result == {"arima": 111.0, "sarima": 222.0, "drift": 0.25}
            assert [args.args[0] for args in load_or_train.call_args_list] == [
                Path("models") / "arima_Australia.pickle",
                Path("models") / "sarima_Australia.pickle",
            ]
            predict_mock.assert_has_calls(
                [
                    call(arima_model, "arima", 3, 5, 90.0),
                    call(sarima_model, "sarima", 3, 5, 90.0),
                ]
            )
            to_csv.assert_called_once_with(
                Path("output") / "5 predictions_Australia.csv"
            )
            drift_input = get_wasserstein_distance.call_args.args[0]
            np.testing.assert_array_equal(
                drift_input,
                np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0]).reshape(-1, 1),
            )
            assert get_wasserstein_distance.call_args.kwargs == {"batch_size": 200}

    @pytest.mark.integration
    @pytest.mark.slow
    class TestIntegration:
        """Real model-fitting tests executed against the pre-built fixture CSVs.

        Both tests share the same ``arima_dirs`` fixture (class-scoped): the first
        test trains and serialises the models; the second test exercises the
        load-from-cache path.
        """

        def test_model_train_saves_arima_and_sarima_pickles(
            self, arima_dirs: tuple[Path, Path]
        ) -> None:
            """model() persists both arima.pickle and sarima.pickle on first run."""
            output_dir, model_dir = arima_dirs
            with (
                patch(_OUTPUT_TARGET, output_dir),
                patch(_MODELS_TARGET, model_dir),
            ):
                model("2018-11-20", 30, None)
            assert (model_dir / "arima.pickle").exists()
            assert (model_dir / "sarima.pickle").exists()

        def test_model_predict_returns_arima_and_sarima_keys(
            self, arima_dirs: tuple[Path, Path]
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
