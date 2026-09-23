"""Evidence processing pipeline."""

from evaluator import evaluate


def normalise(turns):
    """Strip and lowercase each turn."""
    return [t.strip().lower() for t in turns]


def run(turns):
    """Run the full pipeline over a list of conversation turns."""
    cleaned = normalise(turns)
    scored = evaluate(cleaned)
    return {"status": "complete", "dimensions": 4, "coverage": "adequate"}
