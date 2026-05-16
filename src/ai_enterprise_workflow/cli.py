"""Command-line entrypoint for the AI Enterprise Workflow service."""

from __future__ import annotations

import argparse
import json
import sys
from argparse import ArgumentParser, Namespace

# ── ingest ────────────────────────────────────────────────────────────────────


def setup_ingest(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:  # type: ignore[reportPrivateUsage]
    """Register the 'ingest' subcommand parser.

    Args:
        subparsers: The subparser action group to add the 'ingest' command to.

    Examples:
        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> subs = parser.add_subparsers(dest="subcommand")
        >>> setup_ingest(subs)
        >>> args = parser.parse_args(["ingest", "--force"])
        >>> args.force
        True
    """
    parser = subparsers.add_parser("ingest", help="Run the data ingestion pipeline.")
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-run the pipeline even if output files already exist.",
    )
    parser.set_defaults(func=execute_ingest)


def execute_ingest(args: Namespace) -> int:
    """Execute the ingest subcommand.

    Args:
        args: Parsed namespace with ``force: bool``.

    Returns:
        0 on success; 1 on unhandled exception.

    Notes:
        Prints error messages to ``sys.stderr`` on failure.

    Examples:
        >>> from argparse import Namespace
        >>> from unittest.mock import patch
        >>> ns = Namespace(force=False)
        >>> with patch("ai_enterprise_workflow.ingestion.pipeline.ingest"):
        ...     execute_ingest(ns)
        0
    """
    from ai_enterprise_workflow.ingestion.pipeline import ingest  # noqa: PLC0415

    try:
        ingest(force=args.force)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ── train ─────────────────────────────────────────────────────────────────────


def setup_train(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:  # type: ignore[reportPrivateUsage]
    """Register the 'train' subcommand parser.

    Args:
        subparsers: The subparser action group to add the 'train' command to.

    Examples:
        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> subs = parser.add_subparsers(dest="subcommand")
        >>> setup_train(subs)
        >>> args = parser.parse_args(["train", "--date", "2019-01-01"])
        >>> args.date
        '2019-01-01'
    """
    parser = subparsers.add_parser(
        "train", help="Train ARIMA/SARIMA models for a given reference date."
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Reference date (YYYY-MM-DD) for model training.",
    )
    parser.set_defaults(func=execute_train)


def execute_train(args: Namespace) -> int:
    """Execute the train subcommand.

    Args:
        args: Parsed namespace with ``date: str``.
            Uses ``duration=30`` and ``country=None`` as fixed defaults.

    Returns:
        0 on success; 1 on unhandled exception.

    Notes:
        Prints the JSON-serialised model result to ``sys.stdout`` on success.
        Prints error messages to ``sys.stderr`` on failure.

    Examples:
        >>> from argparse import Namespace
        >>> from unittest.mock import patch
        >>> ns = Namespace(date="2019-01-01")
        >>> with patch(
        ...     "ai_enterprise_workflow.forecasting.arima.model",
        ...     return_value={"arima": 1.0},
        ... ):
        ...     code = execute_train(ns)
        {"arima": 1.0}
        >>> code
        0
    """
    from ai_enterprise_workflow.forecasting.arima import model  # noqa: PLC0415

    try:
        result = model(args.date, 30, None)
        print(json.dumps(result, default=str))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ── predict ───────────────────────────────────────────────────────────────────


def setup_predict(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:  # type: ignore[reportPrivateUsage]
    """Register the 'predict' subcommand parser.

    Args:
        subparsers: The subparser action group to add the 'predict' command to.

    Examples:
        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> subs = parser.add_subparsers(dest="subcommand")
        >>> setup_predict(subs)
        >>> args = parser.parse_args(["predict", "--date", "2019-01-01"])
        >>> args.date
        '2019-01-01'
    """
    parser = subparsers.add_parser("predict", help="Generate ARIMA/SARIMA forecasts.")
    parser.add_argument(
        "--date",
        required=True,
        help="Reference date (YYYY-MM-DD) for the forecast origin.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Number of days to forecast (default: 30).",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Country name filter; omit for global totals.",
    )
    parser.set_defaults(func=execute_predict)


def execute_predict(args: Namespace) -> int:
    """Execute the predict subcommand.

    Args:
        args: Parsed namespace with ``date: str``, ``duration: int``,
            ``country: str | None``.

    Returns:
        0 on success; 1 on unhandled exception.

    Notes:
        Prints the JSON-serialised model result to ``sys.stdout`` on success.
        Prints error messages to ``sys.stderr`` on failure.

    Examples:
        >>> from argparse import Namespace
        >>> from unittest.mock import patch
        >>> ns = Namespace(date="2019-01-01", duration=30, country=None)
        >>> with patch(
        ...     "ai_enterprise_workflow.forecasting.arima.model",
        ...     return_value={"forecast": [1.0]},
        ... ):
        ...     code = execute_predict(ns)
        {"forecast": [1.0]}
        >>> code
        0
    """
    from ai_enterprise_workflow.forecasting.arima import model  # noqa: PLC0415

    try:
        result = model(args.date, args.duration, args.country)
        print(json.dumps(result, default=str))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ── serve ─────────────────────────────────────────────────────────────────────


def setup_serve(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:  # type: ignore[reportPrivateUsage]
    """Register the 'serve' subcommand parser.

    Args:
        subparsers: The subparser action group to add the 'serve' command to.

    Examples:
        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> subs = parser.add_subparsers(dest="subcommand")
        >>> setup_serve(subs)
        >>> args = parser.parse_args(["serve", "--port", "8080"])
        >>> args.port
        8080
    """
    parser = subparsers.add_parser("serve", help="Start the Flask development server.")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)."
    )
    parser.add_argument(
        "--port", type=int, default=5000, help="Port number (default: 5000)."
    )
    parser.set_defaults(func=execute_serve)


def execute_serve(args: Namespace) -> int:
    """Execute the serve subcommand.

    Args:
        args: Parsed namespace with ``host: str`` and ``port: int``.

    Returns:
        0 on success; 1 on unhandled exception.

    Notes:
        Starts a blocking HTTP server; terminates only on interrupt or error.
        Prints error messages to ``sys.stderr`` on failure.

    Examples:
        >>> from argparse import Namespace
        >>> from unittest.mock import patch
        >>> ns = Namespace(host="127.0.0.1", port=5000)
        >>> with patch("ai_enterprise_workflow.service.api.app.run"):
        ...     execute_serve(ns)
        0
    """
    from ai_enterprise_workflow.service.api import app  # noqa: PLC0415

    try:
        app.run(host=args.host, port=args.port)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


# ── entrypoint ────────────────────────────────────────────────────────────────


def main() -> int:
    """Parse arguments and dispatch to the appropriate subcommand executor.

    Returns:
        Process exit code: 0 = success, 1 = unhandled exception,
        2 = argparse error (missing or invalid arguments).

    Notes:
        Prints usage help to ``sys.stdout`` when no subcommand is provided.

    Examples:
        >>> import sys
        >>> from unittest.mock import patch
        >>> with patch.object(sys, "argv", ["cli", "ingest"]):
        ...     with patch("ai_enterprise_workflow.ingestion.pipeline.ingest"):
        ...         main()
        0
    """
    parser = ArgumentParser(
        prog="ai_enterprise_workflow",
        description="AI Enterprise Workflow command-line interface.",
    )
    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")
    setup_ingest(subparsers)
    setup_train(subparsers)
    setup_predict(subparsers)
    setup_serve(subparsers)

    args = parser.parse_args()
    if args.subcommand is None:
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
