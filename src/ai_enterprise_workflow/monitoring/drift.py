"""Wasserstein-distance drift detection utilities."""

from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.stats import wasserstein_distance  # type: ignore[import-untyped]


def get_wasserstein_distance(
    data: npt.NDArray[np.floating[Any]],
    batch_size: int = 1000,
    confidence: float = 0.05,
) -> np.floating[Any]:
    """Estimate the Wasserstein distance for drift detection via bootstrap sampling.

    Args:
        data: 2-D array of observations.
        batch_size: Number of bootstrap iterations.
        confidence: Alpha level controlling the two quantile indices: the
            upper quantile is taken at ``1 - confidence`` and the lower at
            ``confidence``.

    Returns:
        Scalar estimate of the Wasserstein distance.

    Notes:
        Results are non-deterministic because :func:`numpy.random.choice` is
        used for bootstrap sampling. Set ``numpy.random.seed`` before calling
        if reproducibility is required.

    Examples:
        >>> import numpy as np
        >>> data = np.random.randn(100, 2)
        >>> score = get_wasserstein_distance(data, batch_size=20)
        >>> isinstance(float(score), float)
        True
    """
    wasserstein_data = np.zeros(batch_size)
    for batch in range(batch_size):
        samples = round(0.8 * data.shape[0])
        subset_indices: npt.NDArray[np.intp] = np.random.choice(  # pyright: ignore[reportUnknownVariableType]
            data.shape[0], samples, replace=True
        )
        data_batch = data[subset_indices, :]
        wasserstein_data[batch] = wasserstein_distance(
            data.flatten(), data_batch.flatten()
        )
    wasserstein_data.sort()
    return (
        wasserstein_data[int((1 - confidence) * batch_size)]
        + wasserstein_data[int(confidence * batch_size)]
    )
