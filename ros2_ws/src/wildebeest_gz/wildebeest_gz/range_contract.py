"""Dependency-free normalization for the simulated front range sensor."""

import math


def normalize_range(value: float, minimum: float, maximum: float) -> float:
    """Return ROS Range sentinel values for readings outside the contract."""

    if not all(math.isfinite(number) for number in (minimum, maximum)):
        raise ValueError('range limits must be finite')
    if minimum <= 0.0 or maximum <= minimum:
        raise ValueError('range limits must be positive and ordered')
    if math.isnan(value):
        raise ValueError('range value must not be NaN')
    if math.isinf(value):
        return value
    if value < minimum:
        return float('-inf')
    if value > maximum:
        return float('inf')
    return value
