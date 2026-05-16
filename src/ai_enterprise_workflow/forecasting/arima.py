"""ARIMA and SARIMA forecasting models for revenue prediction.

Provides utilities to train and persist ARIMA and SARIMA models on historical
revenue data, generate in-sample and out-of-sample predictions, and run the
full forecast pipeline for a given reference date and duration.

The public entry-point is :func:`model`, which orchestrates data ingestion
(if needed), model training or loading from cache, prediction, and CSV output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from statsmodels.iolib.smpickle import load_pickle  # type: ignore[import-untyped]
from statsmodels.tsa.api import SARIMAX  # type: ignore[import-untyped]
from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.core.log_events import log_predict, log_train
from ai_enterprise_workflow.ingestion.pipeline import ingest

# Module-level aliases
DIRECTORY_OUTPUT: Path = cfg.directory_output
DIRECTORY_MODELS: Path = cfg.directory_models


def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:
    """Return daily revenue rows filtered to a single country.

    Args:
        revenue: DataFrame with ``country``, ``date``, and ``revenue`` columns.
        country: Country name to filter on.

    Returns:
        DataFrame containing only the ``date`` and ``revenue`` columns for
        the requested country, with the index reset.

    Examples:
        >>> import pandas as pd
        >>> df = pd.DataFrame(
        ...     {
        ...         "country": ["UK", "US", "UK"],
        ...         "date": ["2019-01-01", "2019-01-01", "2019-01-02"],
        ...         "revenue": [100.0, 200.0, 150.0],
        ...     }
        ... )
        >>> get_revenue_country(df, "UK").shape
        (2, 2)
    """
    return revenue[revenue["country"] == country].reset_index()[["date", "revenue"]]


def train_ARIMA_model(
    data: pd.Series[float],
    order: tuple[int, int, int],
    directory_models: Path,
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
        Calls :func:`~ai_enterprise_workflow.core.log_events.log_train` to
        record the training event.

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> data = pd.Series(range(1, 61), dtype=float)
        >>> with tempfile.TemporaryDirectory() as tmp:  # doctest: +SKIP
        ...     m = train_ARIMA_model(data, (1, 0, 0), pathlib.Path(tmp))
    """
    arima: Any = ARIMA(data, order=order)
    arima_model: Any = arima.fit()
    if country:
        arima_model.save(str(directory_models / f"arima_{country}.pickle"))
    else:
        arima_model.save(str(directory_models / "arima.pickle"))
    log_train("arima", data.shape, {})
    return arima_model


def train_SARIMA_model(
    data: pd.Series[float],
    order: tuple[int, int, int],
    seasonal_order: tuple[int, int, int, int],
    directory_models: Path,
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
        Calls :func:`~ai_enterprise_workflow.core.log_events.log_train` to
        record the training event.

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> data = pd.Series(range(1, 61), dtype=float)
        >>> with tempfile.TemporaryDirectory() as tmp:  # doctest: +SKIP
        ...     m = train_SARIMA_model(
        ...         data, (1, 0, 0), (0, 1, 1, 12), pathlib.Path(tmp)
        ...     )
    """
    sarima: Any = SARIMAX(data, order=order, seasonal_order=seasonal_order)
    sarima_model: Any = sarima.fit()
    if country:
        sarima_model.save(str(directory_models / f"sarima_{country}.pickle"))  # type: ignore[union-attr]
    else:
        sarima_model.save(str(directory_models / "sarima.pickle"))  # type: ignore[union-attr]
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
        Calls :func:`~ai_enterprise_workflow.core.log_events.log_predict` to
        record the query and prediction result.

    Examples:
        >>> from unittest.mock import MagicMock, patch
        >>> import pandas as pd
        >>> m = MagicMock()
        >>> m.predict.return_value = pd.Series([10.0, 20.0])
        >>> with patch("ai_enterprise_workflow.forecasting.arima.log_predict"):
        ...     preds, total = predict(m, "arima", 0, 1)
        >>> float(total)
        30.0
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
        subsequent calls load the cached pickles via
        :func:`~statsmodels.iolib.smpickle.load_pickle`. Writes prediction
        output to ``5 predictions[_<country>].csv``.

    Examples:
        >>> result = model("2019-01-01", duration=30)  # doctest: +SKIP
        >>> sorted(result.keys())  # doctest: +SKIP
        ['arima', 'sarima']

    See Also:
        :func:`train_ARIMA_model`: Fits and persists the ARIMA model.
        :func:`train_SARIMA_model`: Fits and persists the SARIMA model.
        :func:`predict`: Generates predictions from a fitted model.
        `Workflows — Forecasting Pipeline
        <advanced/workflows.md#forecasting-pipeline>`_:
            End-to-end forecasting workflow walkthrough.
    """
    DIRECTORY_MODELS.mkdir(parents=True, exist_ok=True)
    if not (DIRECTORY_OUTPUT / "4 revenue_total.csv").exists():
        ingest()
    revenue_countries = pd.read_csv(DIRECTORY_OUTPUT / "3 revenue_country.csv")
    revenue_total = pd.read_csv(DIRECTORY_OUTPUT / "4 revenue_total.csv")

    if country:
        revenue = get_revenue_country(revenue_countries, country)
        file_suffix = "_" + country
    else:
        revenue = revenue_total
        file_suffix = ""

    order = (2, 1, 2)
    seasonal_order = (2, 1, 2, 30)

    if country:
        arima_pickle = DIRECTORY_MODELS / f"arima_{country}.pickle"
        if arima_pickle.exists():
            arima_model = load_pickle(str(arima_pickle))
        else:
            arima_model = train_ARIMA_model(
                revenue["revenue"], order, DIRECTORY_MODELS, country
            )
        sarima_pickle = DIRECTORY_MODELS / f"sarima_{country}.pickle"
        if sarima_pickle.exists():
            sarima_model = load_pickle(str(sarima_pickle))
        else:
            sarima_model = train_SARIMA_model(
                revenue["revenue"], order, seasonal_order, DIRECTORY_MODELS, country
            )
    else:
        arima_pickle = DIRECTORY_MODELS / "arima.pickle"
        if arima_pickle.exists():
            arima_model = load_pickle(str(arima_pickle))
        else:
            arima_model = train_ARIMA_model(revenue["revenue"], order, DIRECTORY_MODELS)
        sarima_pickle = DIRECTORY_MODELS / "sarima.pickle"
        if sarima_pickle.exists():
            sarima_model = load_pickle(str(sarima_pickle))
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

    revenue.to_csv(DIRECTORY_OUTPUT / ("5 predictions" + file_suffix + ".csv"))

    return {"arima": arima_result, "sarima": sarima_result}
