import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evaluator import classify, confidence, evaluate, merge_profiles  # noqa: E402
from pipeline import coverage, extract_signals, run  # noqa: E402


# --- differentiation: opposite inputs must produce opposite output ---------

def test_opposite_evidence_produces_opposite_bands():
    high = evaluate({"signals": {"table_request": 9, "diagram_request": 4}})
    low = evaluate({"signals": {"wall_of_text_complaint": 9, "too_much_detail": 4}})
    assert high["visual_scaffolding"] == "high"
    assert low["text_density"] == "low"
    assert high != low


def test_absent_evidence_yields_unknown_not_a_default():
    result = evaluate({"signals": {}})
    assert set(result.values()) == {"unknown"}


def test_evidence_volume_changes_confidence():
    assert confidence(100, 20) > confidence(10, 2) > confidence(1, 1)


# --- negative cases --------------------------------------------------------

def test_merge_rejects_an_invalid_band():
    with pytest.raises(ValueError, match="unknown band"):
        merge_profiles({}, {"text_density": "extreme"})


def test_confidence_of_no_sample_is_zero():
    assert confidence(0, 5) == 0.0
    assert confidence(5, 0) == 0.0


def test_unrecognised_signals_are_ignored_not_counted():
    assert evaluate({"signals": {"made_up_signal": 50}}) == evaluate({"signals": {}})


# --- merge semantics -------------------------------------------------------

def test_known_band_beats_unknown_in_either_direction():
    assert merge_profiles({"a": "unknown"}, {"a": "high"})["a"] == "high"
    assert merge_profiles({"a": "high"}, {"a": "unknown"})["a"] == "high"


def test_conflicting_bands_collapse_to_medium():
    assert merge_profiles({"a": "high"}, {"a": "low"})["a"] == "medium"


# --- classify boundaries ---------------------------------------------------

@pytest.mark.parametrize(
    "net,total,expected",
    [(0, 0, "unknown"), (10, 10, "high"), (-10, 10, "low"), (1, 10, "medium")],
)
def test_classify_boundaries(net, total, expected):
    assert classify(net, total) == expected


# --- pipeline --------------------------------------------------------------

def test_extract_signals_counts_real_occurrences():
    turns = ["show me as a table", "as a table again", "that was too long"]
    assert extract_signals(turns) == {"table_request": 2, "too_long_complaint": 1}


def test_coverage_is_honest_about_thin_evidence():
    assert coverage(["one turn"], {"table_request": 1}) == "thin"


def test_run_threads_input_through_to_bands():
    out = run(["  Just tell me  ", "just tell me", "JUST TELL ME"])
    assert out["turns"] == 3
    assert out["signals"] == {"just_tell_me": 3}
    assert out["bands"]["decision_directness"] == "high"
    assert out["coverage"] == "thin"
