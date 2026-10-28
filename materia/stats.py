"""Wilson score interval. Every percentage in this project carries one."""
from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n, in percent."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo = max(0.0, (centre - margin) / denom * 100)
    hi = min(100.0, (centre + margin) / denom * 100)
    return (lo, hi)


def wilson_str(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    pct = 100 * k / n if n else 0.0
    return f"{k}/{n} = {pct:.1f}% [{lo:.1f}, {hi:.1f}]"
