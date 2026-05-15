"""Data ingestion pipeline for loading and preprocessing invoice data."""

import os
import re

import pandas as pd
from tqdm import tqdm

from ai_enterprise_workflow.core.config import (
    DIRECTORY_INPUT,
    DIRECTORY_OUTPUT,
    key_names,
    key_types,
    keys,
)
from ai_enterprise_workflow.core.logging import log_ingest


def get_data(
    keys: tuple[str, ...],
    key_names: dict[str, str],
    directory_data: str,
    directory_output: str,
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
        Reads all files in ``directory_data`` via ``os.listdir``. Persists the
        combined result to ``0 data.csv`` in ``directory_output``.
    """
    # Initialise dataframe with desired column names
    data = pd.DataFrame(columns=keys, dtype=int)
    for file_name in tqdm(os.listdir(directory_data)):
        with open(directory_data + file_name) as file:
            # Read JSON into pandas dataframe
            transactions = pd.read_json(file)
        # Rename column names using desired mappings
        transactions.rename(columns=key_names, inplace=True)
        # Concatenate transactions from file to master dataframe
        data = pd.concat([data, transactions])
    # Persist transactions in CSV file
    data.to_csv(directory_output + "0 data.csv", index=False)
    return data


def _to_digits(value: object) -> str:
    """Strip all non-digit characters from a value's string representation."""
    return re.sub("[^0-9]", "", str(value))


def clean_data(
    data: pd.DataFrame,
    keys: tuple[str, ...],
    key_types: dict[str, type[int] | type[float] | type[str]],
    directory_output: str,
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
    """
    data = data.copy()
    # Remove duplicate rows
    data.drop_duplicates(inplace=True)
    # Replace null with -1
    data.fillna(value=-1, inplace=True)
    # Some features have non-numeric characters; remove those characters from string
    data["invoice_id"] = data["invoice_id"].apply(_to_digits)
    data["stream_id"] = data["stream_id"].apply(_to_digits)
    # Replace empty strings with -1
    data = data.replace(r"^\s*$", -1, regex=True)
    # Update data types to reduce memory consumption
    for key in keys:
        data[key] = data[key].astype(key_types[key])
    # Persist cleaned transactions in CSV file
    data.to_csv(directory_output + "1 data_cleaned.csv", index=False)
    return data


def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:
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
    data.to_csv(directory_output + "2 data_engineered.csv", index=False)
    return data


def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> None:
    """Aggregate transaction prices into daily revenue grouped by country.

    Args:
        data: Prepared DataFrame containing ``country``, ``date``, and
            ``price`` columns.
        directory_output: Path to the directory where output CSVs are written.

    Notes:
        Persists the result to ``3 revenue_country.csv`` in
        ``directory_output``.
    """
    # Sum transaction prices by country and date
    revenue = data.groupby(["country", "date"])["price"].sum().reset_index()
    revenue.rename(columns={"price": "revenue"}, inplace=True)
    # Persist calculated daily revenue by country in CSV file
    revenue.to_csv(directory_output + "3 revenue_country.csv", index=False)


def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:
    """Aggregate transaction prices into total daily revenue across all countries.

    Args:
        data: Prepared DataFrame containing ``date`` and ``price`` columns.
        directory_output: Path to the directory where output CSVs are written.

    Notes:
        Persists the result to ``4 revenue_total.csv`` in ``directory_output``.
        The ``date`` column is used as the DataFrame index in the output file.
    """
    # Sum transaction prices by date
    revenue = data.groupby(["date"])["price"].sum().reset_index()
    revenue.set_index("date", inplace=True)
    revenue.rename(columns={"price": "revenue"}, inplace=True)
    # Persist calculated daily total revenue in CSV file
    revenue.to_csv(directory_output + "4 revenue_total.csv")


def ingest(force: bool = False) -> None:
    """Run the full ingestion pipeline, writing processed CSVs to the output directory.

    Args:
        force: If True, re-run even when output files already exist.

    Notes:
        Creates ``DIRECTORY_OUTPUT`` if it does not exist. On a full run,
        writes up to five CSVs (``0``-``4``) and calls :func:`log_ingest`
        to record the event. Short-circuits when the terminal output file
        already exists and ``force`` is ``False``.
    """
    if not os.path.exists(DIRECTORY_OUTPUT):
        os.makedirs(DIRECTORY_OUTPUT)
    if force or not os.path.exists(DIRECTORY_OUTPUT + "4 revenue_total.csv"):
        print("Reading data...")
        data = get_data(keys, key_names, DIRECTORY_INPUT, DIRECTORY_OUTPUT)
        print("Cleaning data...")
        data = clean_data(data, keys, key_types, DIRECTORY_OUTPUT)
        print("Preparing features...")
        data = prepare_data(data, DIRECTORY_OUTPUT)
        print("Calculating revenue by country...")
        calculate_revenue_country(data, DIRECTORY_OUTPUT)
        print("Calculating total revenue...")
        calculate_revenue_total(data, DIRECTORY_OUTPUT)
        print("Done.")
        log_ingest(data.shape)
