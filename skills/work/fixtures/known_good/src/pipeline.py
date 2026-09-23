"""Evidence processing pipeline."""

from evaluator import evaluate


def normalise(turns):
    """Strip and lowercase each turn, dropping empties."""
    return [t.strip().lower() for t in turns if t and t.strip()]


def extract_signals(turns):
    """Count occurrences of each known signal phrase across ``turns``."""
    phrases = {
        "table_request": "as a table",
        "diagram_request": "draw a diagram",
        "too_long_complaint": "too long",
        "wall_of_text_complaint": "wall of text",
        "just_tell_me": "just tell me",
        "give_me_options": "give me options",
        "show_your_work": "show your work",
        "too_much_detail": "too much detail",
    }
    counts = {}
    for name, phrase in phrases.items():
        hits = sum(1 for t in turns if phrase in t)
        if hits:
            counts[name] = hits
    return counts


def coverage(turns, signals):
    """Report how much evidence was actually found."""
    if len(turns) < 40 or len(signals) < 5:
        return "thin"
    if sum(signals.values()) < 20:
        return "partial"
    return "adequate"


def run(turns):
    """Run the full pipeline over a list of conversation turns."""
    cleaned = normalise(turns)
    signals = extract_signals(cleaned)
    bands = evaluate({"signals": signals})
    return {
        "turns": len(cleaned),
        "signals": signals,
        "coverage": coverage(cleaned, signals),
        "bands": bands,
    }
