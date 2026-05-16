"""Unit tests for monitoring.drift.get_wasserstein_distance."""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from ai_enterprise_workflow.monitoring.drift import get_wasserstein_distance


@pytest.mark.unit
class TestWassersteinDistance:
    def test_constant_data_returns_low_score(self) -> None:
        """A constant-value array has near-zero Wasserstein drift."""
        data: npt.NDArray[np.floating[Any]] = np.ones((100, 1), dtype=np.float64)
        score = get_wasserstein_distance(data, batch_size=50)
        assert float(score) < 0.05

    def test_shifted_data_returns_positive_score(self) -> None:
        """Clearly shifted distribution produces a positive drift score."""
        rng = np.random.default_rng(42)
        data: npt.NDArray[np.floating[Any]] = np.concatenate(
            [rng.normal(0.0, 0.1, (50, 1)), rng.normal(10.0, 0.1, (50, 1))]
        ).astype(np.float64)
        score = get_wasserstein_distance(data, batch_size=50)
        assert float(score) > 0.0

    def test_empty_data_raises(self) -> None:
        """Empty input raises an error."""
        empty: npt.NDArray[np.floating[Any]] = np.empty((0, 1), dtype=np.float64)
        with pytest.raises((IndexError, ValueError)):
            get_wasserstein_distance(empty, batch_size=10)
