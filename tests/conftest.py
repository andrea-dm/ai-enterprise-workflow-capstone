"""Shared pytest fixtures for the ai_enterprise_workflow test suite."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from flask.testing import FlaskClient

from ai_enterprise_workflow.service.api import create_app


@pytest.fixture
def flask_client() -> Generator[FlaskClient, None, None]:
    """Yield a Flask test client backed by a fresh app instance.

    Yields:
        FlaskClient: a configured Flask test client with ``TESTING=True``.

    Notes:
        Uses the :func:`create_app` factory with ``{"TESTING": True}`` to
        ensure each test receives an isolated Flask application instance.
    """
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client
