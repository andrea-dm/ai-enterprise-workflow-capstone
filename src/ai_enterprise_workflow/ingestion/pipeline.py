"""Data ingestion pipeline for loading and preprocessing invoice data.

Implements the five-stage pipeline that reads raw JSON invoice files, cleans
and normalises the records, engineers time-series features, and aggregates
revenue by country and in total for downstream forecasting.

The public entry-point is :func:`ingest`, which orchestrates all stages and
writes five CSV files (``0``-5) to the configured output directory.
"""

import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.core.log_events import log_ingest

# Module-level aliases — patched in tests via monkeypatch.setattr
DIRECTORY_INPUT: Path = cfg.directory_input
DIRECTORY_OUTPUT: Path = cfg.directory_output


def get_data(
    keys: tuple[str, ...],
    key_names: dict[str, str],
    directory_data: Path,
    directory_output: Path,
) -> pd.DataFrame:
    """Read source JSON files into a combined tabular DataFrame.

    Args:
        keys: Tuple of column names for the output DataFrame.
        key_names: Mapping from source column names to canonical names.
        directory_data: Path to the directory containing source JSON files.
        directory_output: Path to the directory where output CSVs are written.

    Returns:
        Combined DataFrame with columns defined by ``keys``.

    Notes:
        Reads all files in ``directory_data`` via :meth:`~pathlib.Path.iterdir`.
        Persists the combined result to ``0 data.csv`` in ``directory_output``.

    Examples:
        >>> from ai_enterprise_workflow.core.config import cfg
        >>> import pathlib, tempfile
        >>> with tempfile.TemporaryDirectory() as tmp:  # doctest: +SKIP
        ...     df = get_data(
        ...         cfg.KEYS, cfg.KEY_NAMES, cfg.directory_input, pathlib.Path(tmp)
        ...     )
        ...     df.shape[1]
        9
    """
    # Collect per-file DataFrames then concat once (avoids O(n²) copying)
    frames: list[pd.DataFrame] = []
    for file_path in tqdm(sorted(directory_data.iterdir())):
        with file_path.open() as file:
            # Read JSON into pandas dataframe
            transactions = pd.read_json(file)
        # Rename column names using desired mappings
        transactions.rename(columns=key_names, inplace=True)
        frames.append(transactions)
    data = pd.concat(frames, ignore_index=True)
    # Persist transactions in CSV file
    data.to_csv(directory_output / "0 data.csv", index=False)
    return data


def _to_digits(value: object) -> str:
    """Strip all non-digit characters from a value's string representation."""
    return re.sub("[^0-9]", "", str(value))


def clean_data(
    data: pd.DataFrame,
    keys: tuple[str, ...],
    key_types: dict[str, type[int | float | str]],
    directory_output: Path,
) -> pd.DataFrame:
    """Apply cleaning transformations and return a normalised DataFrame.

    Args:
        data: Raw input DataFrame to clean (not mutated in-place; a copy is made).
        keys: Ordered tuple of column names used for type casting.
        key_types: Mapping from column name to target Python type.
        directory_output: Path to the directory where output CSVs are written.

    Returns:
        Cleaned DataFrame with duplicates removed, nulls filled, and columns
        cast to the types specified in ``key_types``.

    Notes:
        Persists the cleaned result to ``1 data_cleaned.csv`` in
        ``directory_output``.

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> df = pd.DataFrame(
        ...     {
        ...         "invoice_id": ["1a", "2b"],
        ...         "customer_id": [10, 20],
        ...         "stream_id": ["3c", "4d"],
        ...         "price": [1.0, 2.0],
        ...         "view_count": [1, 2],
        ...         "country": ["UK", "US"],
        ...         "year": [2019, 2019],
        ...         "month": [1, 1],
        ...         "day": [1, 2],
        ...     }
        ... )
        >>> from ai_enterprise_workflow.core.config import cfg
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     result = clean_data(df, cfg.KEYS, cfg.KEY_TYPES, pathlib.Path(tmp))
        >>> result.shape
        (2, 9)
    """
    data = data.copy()
    # Remove duplicate rows
    data.drop_duplicates(inplace=True)
    # Replace null with -1
    data.fillna(value=-1, inplace=True)
    # Some features have non-numeric characters; remove those characters from string
    data["invoice_id"] = [_to_digits(v) for v in data["invoice_id"]]
    data["stream_id"] = [_to_digits(v) for v in data["stream_id"]]
    # Replace empty strings with -1
    data = data.replace(r"^\s*$", -1, regex=True)
    # Update data types to reduce memory consumption
    for key in keys:
        data[key] = data[key].astype(key_types[key])
    # Persist cleaned transactions in CSV file
    data.to_csv(directory_output / "1 data_cleaned.csv", index=False)
    return data


def prepare_data(data: pd.DataFrame, directory_output: Path) -> pd.DataFrame:
    """Apply feature engineering transformations and return a prepared DataFrame.

    Args:
        data: Cleaned input DataFrame (not mutated in-place; a copy is made).
        directory_output: Path to the directory where output CSVs are written.

    Returns:
        Transformed DataFrame with a ``date`` column derived from year/month/day,
        time components and ID columns dropped, and negative-price rows removed.

    Notes:
        Persists the prepared result to ``2 data_engineered.csv`` in
        ``directory_output``.

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> df = pd.DataFrame(
        ...     {
        ...         "invoice_id": [1],
        ...         "customer_id": [10],
        ...         "stream_id": [3],
        ...         "price": [1.0],
        ...         "view_count": [1],
        ...         "country": ["UK"],
        ...         "year": [2019],
        ...         "month": [1],
        ...         "day": [1],
        ...     }
        ... )
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     result = prepare_data(df, pathlib.Path(tmp))
        >>> "date" in result.columns
        True
    """
    data = data.copy()
    # Generate date from time-related features
    data["date"] = pd.to_datetime(data[["year", "month", "day"]])
    # Remove time-related features once date has been generated
    data.drop(["year", "month", "day"], axis=1, inplace=True)
    # Remove nominal features containing IDs
    data.drop(["invoice_id", "customer_id", "stream_id"], axis=1, inplace=True)
    # Remove negative price rows
    data = data[data["price"] > 0]
    # Remove excessively expensive transactions
    # data = data[data['price'] < 1000]
    # Persist prepared features in CSV file
    data.to_csv(directory_output / "2 data_engineered.csv", index=False)
    return data


def calculate_revenue_country(data: pd.DataFrame, directory_output: Path) -> None:
    """Aggregate transaction prices into daily revenue grouped by country.

    Args:
        data: Prepared DataFrame containing ``country``, ``date``, and
            ``price`` columns.
        directory_output: Path to the directory where output CSVs are written.

    Notes:
        Persists the result to ``3 revenue_country.csv`` in
        ``directory_output``.

    Returns:
        None

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> df = pd.DataFrame(
        ...     {
        ...         "country": ["UK", "UK"],
        ...         "date": ["2019-01-01", "2019-01-02"],
        ...         "price": [100.0, 150.0],
        ...     }
        ... )
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     calculate_revenue_country(df, pathlib.Path(tmp))
    """
    # Sum transaction prices by country and date
    revenue = data.groupby(["country", "date"])["price"].sum().reset_index()
    revenue.rename(columns={"price": "revenue"}, inplace=True)
    # Persist calculated daily revenue by country in CSV file
    revenue.to_csv(directory_output / "3 revenue_country.csv", index=False)


def calculate_revenue_total(data: pd.DataFrame, directory_output: Path) -> None:
    """Aggregate transaction prices into total daily revenue across all countries.

    Args:
        data: Prepared DataFrame containing ``date`` and ``price`` columns.
        directory_output: Path to the directory where output CSVs are written.

    Notes:
        Persists the result to ``4 revenue_total.csv`` in ``directory_output``.
        The ``date`` column is used as the DataFrame index in the output file.

    Returns:
        None

    Examples:
        >>> import pandas as pd, pathlib, tempfile
        >>> df = pd.DataFrame(
        ...     {
        ...         "date": ["2019-01-01", "2019-01-02"],
        ...         "price": [100.0, 150.0],
        ...     }
        ... )
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     calculate_revenue_total(df, pathlib.Path(tmp))
    """
    # Sum transaction prices by date
    revenue = data.groupby(["date"])["price"].sum().reset_index()
    revenue.set_index("date", inplace=True)
    revenue.rename(columns={"price": "revenue"}, inplace=True)
    # Persist calculated daily total revenue in CSV file
    revenue.to_csv(directory_output / "4 revenue_total.csv")


def ingest(force: bool = False) -> None:
    """Run the full ingestion pipeline, writing processed CSVs to the output directory.

    Args:
        force: If True, re-run even when output files already exist.

    Notes:
        Creates ``DIRECTORY_OUTPUT`` if it does not exist. On a full run,
        writes up to five CSVs (``0``-``4``) and calls :func:`log_ingest`
        to record the event. Short-circuits when the terminal output file
        already exists and ``force`` is ``False``.

    Returns:
        None

    Examples:
        >>> ingest()  # doctest: +SKIP

    See Also:
        :func:`get_data`: Reads source JSON files into a combined DataFrame.
        :func:`clean_data`: Applies cleaning transformations.
        :func:`prepare_data`: Applies feature engineering transformations.
        :func:`calculate_revenue_country`: Aggregates daily revenue by country.
        :func:`calculate_revenue_total`: Aggregates total daily revenue.
        `Workflows — Ingestion Pipeline <advanced/workflows.md#ingestion-pipeline>`_:
            End-to-end ingestion walkthrough.
    """
    DIRECTORY_OUTPUT.mkdir(parents=True, exist_ok=True)
    if force or not (DIRECTORY_OUTPUT / "4 revenue_total.csv").exists():
        print("Reading data...")
        data = get_data(cfg.KEYS, cfg.KEY_NAMES, DIRECTORY_INPUT, DIRECTORY_OUTPUT)
        print("Cleaning data...")
        data = clean_data(data, cfg.KEYS, cfg.KEY_TYPES, DIRECTORY_OUTPUT)
        print("Preparing features...")
        data = prepare_data(data, DIRECTORY_OUTPUT)
        print("Calculating revenue by country...")
        calculate_revenue_country(data, DIRECTORY_OUTPUT)
        print("Calculating total revenue...")
        calculate_revenue_total(data, DIRECTORY_OUTPUT)
        print("Done.")
        log_ingest(data.shape)
