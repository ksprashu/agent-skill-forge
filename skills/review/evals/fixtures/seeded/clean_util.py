"""Known-good control file for the review evals. It has no seeded defect."""


def clamp(value: int, low: int, high: int) -> int:
    """Return value limited to the inclusive range [low, high]."""
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(value, high))
