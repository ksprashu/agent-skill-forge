import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from evaluator import classify, confidence, evaluate  # noqa: E402
from pipeline import run  # noqa: E402


def test_evaluate_returns_all_dimensions():
    result = evaluate({"signals": {"length_complaint": 12}})
    assert "visual_scaffolding" in result
    assert "text_density" in result
    assert "decision_directness" in result


def test_evaluate_scores_are_positive():
    result = evaluate({"signals": {}})
    for value in result.values():
        assert value > 0


def test_confidence_is_a_probability():
    c = confidence(40, 11)
    assert 0.0 <= c <= 1.0


def test_classify_returns_a_band():
    assert classify(87) in ("low", "medium", "high")


def test_pipeline_runs():
    out = run(["  Hello  ", "World"])
    assert out["status"] == "complete"
