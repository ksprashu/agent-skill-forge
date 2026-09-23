"""Cognitive evidence evaluator.

Computes per-dimension ordinal bands from harvested conversation evidence.
Every output is derived from the supplied evidence; an absent signal yields
``unknown`` rather than a default.
"""

BANDS = ("low", "medium", "high", "unknown")

# Signal name -> dimension it contributes to.
SIGNAL_MAP = {
    "table_request": "visual_scaffolding",
    "diagram_request": "visual_scaffolding",
    "too_long_complaint": "text_density",
    "wall_of_text_complaint": "text_density",
    "just_tell_me": "decision_directness",
    "give_me_options": "decision_directness",
    "show_your_work": "evidence_depth",
    "too_much_detail": "evidence_depth",
}

# Signals that push a dimension toward ``low`` rather than ``high``.
NEGATIVE_SIGNALS = frozenset(
    {"wall_of_text_complaint", "give_me_options", "too_much_detail"}
)


def classify(net, total):
    """Map a net signal count onto an ordinal band.

    ``net`` is positive-minus-negative evidence, ``total`` is the volume of
    evidence behind it. No evidence means ``unknown``, never a default band.
    """
    if total <= 0:
        return "unknown"
    ratio = net / total
    if ratio >= 0.34:
        return "high"
    if ratio <= -0.34:
        return "low"
    return "medium"


def evaluate(evidence):
    """Compute one ordinal band per dimension from ``evidence``.

    ``evidence`` is a mapping with a ``signals`` key of ``{name: count}``.
    Dimensions with no supporting signal are reported ``unknown``.
    """
    signals = (evidence or {}).get("signals", {})
    dimensions = sorted(set(SIGNAL_MAP.values()))
    tally = {dim: [0, 0] for dim in dimensions}

    for name, count in signals.items():
        dim = SIGNAL_MAP.get(name)
        if dim is None:
            continue
        sign = -1 if name in NEGATIVE_SIGNALS else 1
        tally[dim][0] += sign * int(count)
        tally[dim][1] += abs(int(count))

    return {dim: classify(net, total) for dim, (net, total) in tally.items()}


def confidence(sample_size, signal_count):
    """Confidence in an evaluation, from sample volume and signal density.

    Saturates at 0.95: no amount of chat log makes this an instrument.
    """
    if sample_size <= 0 or signal_count <= 0:
        return 0.0
    volume = min(1.0, sample_size / 100.0)
    density = min(1.0, signal_count / 20.0)
    return round(0.95 * volume * density, 4)


def merge_profiles(base, incoming):
    """Merge ``incoming`` over ``base``, preferring known bands.

    A known band never loses to ``unknown``; two conflicting known bands
    collapse to ``medium`` rather than silently picking a side.
    """
    merged = dict(base or {})
    for dim, band in (incoming or {}).items():
        if band not in BANDS:
            raise ValueError(f"unknown band {band!r} for dimension {dim!r}")
        current = merged.get(dim, "unknown")
        if current == "unknown" or current == band:
            merged[dim] = band
        elif band == "unknown":
            continue
        else:
            merged[dim] = "medium"
    return merged
