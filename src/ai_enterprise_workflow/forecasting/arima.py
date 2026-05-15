"""ARIMA and SARIMA forecasting models for revenue prediction."""

import os
import pickle

import pandas as pd
from statsmodels.tsa.api import SARIMAX
from statsmodels.tsa.arima.model import ARIMA

from ai_enterprise_workflow.core.config import (
    DIRECTORY_MODELS,
    DIRECTORY_OUTPUT,
)
from ai_enterprise_workflow.core.logging import log_predict, log_train
from ai_enterprise_workflow.ingestion.pipeline import ingest


def get_revenue_country(revenue, country):
    """Get daily revenue data for given country"""
    return revenue[revenue["country"] == country].reset_index()[["date", "revenue"]]


def train_ARIMA_model(data, order, directory_models, country=None):
    """Train an auto-regressive, integrating, moving-average (ARIMA) model"""
    arima = ARIMA(data, order=order)
    arima_model = arima.fit()
    if country:
        arima_model.save(directory_models + "arima_" + country + ".pickle")
    else:
        arima_model.save(directory_models + "arima.pickle")
    log_train("arima", data.shape, {})
    return arima_model


def train_SARIMA_model(data, order, seasonal_order, directory_models, country=None):
    """Train a seasonal auto-regressive, integrating, moving-average (SARIMA) model"""
    sarima = SARIMAX(data, order=order, seasonal_order=seasonal_order)
    sarima_model = sarima.fit()
    if country:
        sarima_model.save(directory_models + "sarima_" + country + ".pickle")  # type: ignore[union-attr]
    else:
        sarima_model.save(directory_models + "sarima.pickle")  # type: ignore[union-attr]
    log_train("sarima", data.shape, {})
    return sarima_model


def predict(model, name, start, end, actual=None):
    """Generate forecasted predictions using trained model"""
    predictions = model.predict(start=start, end=end, dynamic=True)
    predictions_sum = predictions.sum()
    log_predict(
        name,
        {"start": start, "end": end},
        {"revenue_predicted": predictions_sum, "revenue_actual": actual},
    )
    return predictions, predictions_sum


def model(date, duration=30, country=None):  # noqa: PLR0912
    """Run the full ARIMA/SARIMA forecast pipeline for the given date and duration.

    Args:
        date: Reference date string (YYYY-MM-DD) used as the forecast origin.
        duration: Number of days to forecast.
        country: Optional country name; if omitted, totals across all countries.

    Returns:
        Dictionary with ARIMA and SARIMA prediction results.
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

    start = revenue.index[revenue["date"] == date].tolist()[0] + 1
    end = start + duration

    new_index = set(revenue.index.tolist()) | set(range(start, end))
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
