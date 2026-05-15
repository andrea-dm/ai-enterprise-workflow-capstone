"""ARIMA and SARIMA forecasting models for revenue prediction."""

from __future__ import annotations

import os
import pickle
from typing import Any

import pandas as pd
from statsmodels.tsa.api import SARIMAX  # type: ignore[import-untyped]
from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]

from ai_enterprise_workflow.core.config import (
    DIRECTORY_MODELS,
    DIRECTORY_OUTPUT,
)
from ai_enterprise_workflow.core.logging import log_predict, log_train
from ai_enterprise_workflow.ingestion.pipeline import ingest


def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:
    """Return daily revenue rows filtered to a single country.

    Args:
        revenue: DataFrame with ``country``, ``date``, and ``revenue`` columns.
        country: Country name to filter on.

    Returns:
        DataFrame containing only the ``date`` and ``revenue`` columns for
        the requested country, with the index reset.
    """
    return revenue[revenue["country"] == country].reset_index()[["date", "revenue"]]


def train_ARIMA_model(
    data: pd.Series[float],
    order: tuple[int, int, int],
    directory_models: str,
    country: str | None = None,
) -> Any:
    """Fit an ARIMA model and persist it to disk.

    Args:
        data: Time-series of revenue values used for training.
        order: ARIMA ``(p, d, q)`` order tuple.
        directory_models: Directory path where the fitted model is saved.
        country: Optional country suffix appended to the pickle filename.
            If ``None``, the file is saved as ``arima.pickle``.

    Returns:
        Fitted ARIMA model instance.

    Notes:
        Saves the trained model as a pickle file in ``directory_models``.
        Calls :func:`~ai_enterprise_workflow.core.logging.log_train` to
        record the training event.
    """
    arima: Any = ARIMA(data, order=order)
    arima_model: Any = arima.fit()
    if country:
        arima_model.save(directory_models + "arima_" + country + ".pickle")
    else:
        arima_model.save(directory_models + "arima.pickle")
    log_train("arima", data.shape, {})
    return arima_model


def train_SARIMA_model(
    data: pd.Series[float],
    order: tuple[int, int, int],
    seasonal_order: tuple[int, int, int, int],
    directory_models: str,
    country: str | None = None,
) -> Any:
    """Fit a SARIMA model and persist it to disk.

    Args:
        data: Time-series of revenue values used for training.
        order: ARIMA ``(p, d, q)`` non-seasonal order tuple.
        seasonal_order: Seasonal ``(P, D, Q, s)`` order tuple.
        directory_models: Directory path where the fitted model is saved.
        country: Optional country suffix appended to the pickle filename.
            If ``None``, the file is saved as ``sarima.pickle``.

    Returns:
        Fitted SARIMA model instance.

    Notes:
        Saves the trained model as a pickle file in ``directory_models``.
        Calls :func:`~ai_enterprise_workflow.core.logging.log_train` to
        record the training event.
    """
    sarima: Any = SARIMAX(data, order=order, seasonal_order=seasonal_order)
    sarima_model: Any = sarima.fit()
    if country:
        sarima_model.save(directory_models + "sarima_" + country + ".pickle")  # type: ignore[union-attr]
    else:
        sarima_model.save(directory_models + "sarima.pickle")  # type: ignore[union-attr]
    log_train("sarima", data.shape, {})
    return sarima_model


def predict(
    model: Any,
    name: str,
    start: int,
    end: int,
    actual: float | None = None,
) -> tuple[Any, Any]:
    """Generate in-sample or out-of-sample predictions from a fitted model.

    Args:
        model: Fitted ARIMA or SARIMA model with a ``predict`` method.
        name: Model identifier string used when logging the prediction event.
        start: First index of the prediction range (inclusive).
        end: Last index of the prediction range (inclusive).
        actual: Observed revenue over the forecast window, used for comparison
            logging. Pass ``None`` when actuals are unavailable.

    Returns:
        A 2-tuple of:

        - ``predictions``: Series of per-period predicted values.
        - ``predictions_sum``: Scalar sum of all predicted values over the window.

    Notes:
        Calls :func:`~ai_enterprise_workflow.core.logging.log_predict` to
        record the query and prediction result.
    """
    predictions = model.predict(start=start, end=end, dynamic=True)
    predictions_sum = predictions.sum()
    log_predict(
        name,
        {"start": start, "end": end},
        {"revenue_predicted": predictions_sum, "revenue_actual": actual},
    )
    return predictions, predictions_sum


def model(date: str, duration: int = 30, country: str | None = None) -> dict[str, Any]:  # noqa: PLR0912
    """Run the full ARIMA/SARIMA forecast pipeline for the given date and duration.

    Args:
        date: Reference date string (YYYY-MM-DD) used as the forecast origin.
        duration: Number of days to forecast.
        country: Optional country name; if omitted, totals across all countries.

    Returns:
        Dictionary with ARIMA and SARIMA prediction results.

    Notes:
        Reads ``3 revenue_country.csv`` and ``4 revenue_total.csv`` from
        ``DIRECTORY_OUTPUT``; calls :func:`ingest` first if the latter is
        absent. Trains and pickles ARIMA and SARIMA models on the first run;
        subsequent calls load the cached pickles. Writes prediction output
        to ``5 predictions[_<country>].csv``.
    """
    if not os.path.exists(DIRECTORY_MODELS):
        os.makedirs(DIRECTORY_MODELS)
    if not os.path.exists(DIRECTORY_OUTPUT + "4 revenue_total.csv"):
        ingest()
    revenue_countries = pd.read_csv(DIRECTORY_OUTPUT + "3 revenue_country.csv")
    revenue_total = pd.read_csv(DIRECTORY_OUTPUT + "4 revenue_total.csv")

    if country:
        revenue = get_revenue_country(revenue_countries, country)
        file_suffix = "_" + country
    else:
        revenue = revenue_total
        file_suffix = ""

    order = (2, 1, 2)
    seasonal_order = (2, 1, 2, 30)

    if country:
        if os.path.exists(DIRECTORY_MODELS + "arima_" + country + ".pickle"):
            with open(DIRECTORY_MODELS + "arima_" + country + ".pickle", "rb") as file:
                arima_model = pickle.load(file)
        else:
            arima_model = train_ARIMA_model(
                revenue["revenue"], order, DIRECTORY_MODELS, country
            )
        if os.path.exists(DIRECTORY_MODELS + "sarima_" + country + ".pickle"):
            with open(DIRECTORY_MODELS + "sarima_" + country + ".pickle", "rb") as file:
                sarima_model = pickle.load(file)
        else:
            sarima_model = train_SARIMA_model(
                revenue["revenue"], order, seasonal_order, DIRECTORY_MODELS, country
            )
    else:
        if os.path.exists(DIRECTORY_MODELS + "arima.pickle"):
            with open(DIRECTORY_MODELS + "arima.pickle", "rb") as file:
                arima_model = pickle.load(file)
        else:
            arima_model = train_ARIMA_model(revenue["revenue"], order, DIRECTORY_MODELS)
        if os.path.exists(DIRECTORY_MODELS + "sarima.pickle"):
            with open(DIRECTORY_MODELS + "sarima.pickle", "rb") as file:
                sarima_model = pickle.load(file)
        else:
            sarima_model = train_SARIMA_model(
                revenue["revenue"], order, seasonal_order, DIRECTORY_MODELS
            )

    start = revenue.index[revenue["date"] == date][0] + 1
    end = start + duration

    new_index = set(revenue.index) | set(range(start, end))
    revenue = revenue.reindex(sorted(new_index))

    actual_result = revenue["revenue"][start:end].sum()
    revenue["forecast_arima"], arima_result = predict(
        arima_model, "arima", start, end, actual_result
    )
    revenue["forecast_sarima"], sarima_result = predict(
        sarima_model, "sarima", start, end, actual_result
    )

    revenue.to_csv(DIRECTORY_OUTPUT + "5 predictions" + file_suffix + ".csv")

    return {"arima": arima_result, "sarima": sarima_result}
