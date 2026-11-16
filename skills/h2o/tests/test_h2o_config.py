"""Checks that the H2O config is valid and that SKILL.md agrees with it."""

import json
import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = json.loads((SKILL_DIR / "swarm.config.json").read_text())
SKILL = (SKILL_DIR / "SKILL.md").read_text()


def _table_rows():
    rows = {}
    for line in SKILL.splitlines():
        match = re.match(r"\|\s*`([a-z-]+)`\s*\|\s*(.+?)\s*\|", line)
        if match:
            rows[match.group(1)] = match.group(2)
    return rows


def test_skill_name_matches_config():
    assert re.search(r"^name: h2o$", SKILL, re.MULTILINE)
    assert CONFIG["name"] == "h2o"


def test_authors_are_hydrogen_high_or_xhigh():
    for name, role in CONFIG["roles"].items():
        if role["kind"] == "author":
            assert role["model"] in {"gemini-4-hydrogen-high", "gemini-4-hydrogen-xhigh"}, name
            assert role.get("escalate_to", role["model"]).startswith("gemini-4-hydrogen-")


def test_reviewers_are_opus_medium_except_security_high():
    policy = CONFIG["model_policy"]
    reviewers = {
        name: role for name, role in CONFIG["roles"].items()
        if role["kind"] == "adversarial_reviewer"
    }
    assert set(reviewers) == {
        "intent-reviewer", "plan-reviewer", "functional-reviewer", "code-reviewer", "security-reviewer",
    }
    for name, role in reviewers.items():
        expected = policy["reviewer_exceptions"].get(name, policy["reviewer_default"])
        assert role["model"] == expected, name
    assert reviewers["security-reviewer"]["model"] == "claude-opus-5-5-high"
    assert policy["reviewer_default"] == "claude-opus-5-5-medium"


def test_code_reviews_run_in_order_and_rework_reruns_all():
    stages = {stage["id"]: stage for stage in CONFIG["stages"]}
    assert stages["functional_review"]["on_good"] == "code_review"
    assert stages["code_review"]["on_good"] == "security_review"
    assert stages["security_review"]["on_good"] == "summary"
    assert CONFIG["loop_policy"]["implement_rework_reruns"] == [
        "functional_review", "code_review", "security_review",
    ]


def test_skill_table_matches_config_models():
    rows = _table_rows()
    for name, role in CONFIG["roles"].items():
        assert name in rows, f"{name} missing from SKILL.md role table"
        assert f"`{role['model']}`" in rows[name], name


def test_stage_transitions_point_at_known_stages():
    ids = {stage["id"] for stage in CONFIG["stages"]} | {"output"}
    for stage in CONFIG["stages"]:
        for key in ("next", "on_good", "on_not_good", "on_design_defect", "on_fail"):
            if key in stage:
                assert stage[key] in ids, (stage["id"], key)
        if stage["owner"] != "coordinator":
            assert stage["owner"] in CONFIG["roles"], stage["id"]


def test_loop_is_capped():
    assert CONFIG["loop_policy"]["max_not_good_per_gate"] == 3
    assert CONFIG["loop_policy"]["on_cap"] == "ask_user_stop_or_continue"


def test_skill_md_fits_the_context_budget():
    assert len(SKILL.splitlines()) <= 200


def test_every_reference_is_explicitly_read():
    """K2: a references/ file nobody is told to read is dead weight."""
    for ref in sorted((SKILL_DIR / "references").glob("*.md")):
        assert re.search(rf"Read `references/{ref.name}`", SKILL), ref.name


def test_full_documentation_exists():
    for name in ("README.md", "DESIGN.md", "scripts/h2o_gate.py"):
        assert (SKILL_DIR / name).is_file(), name


def test_readme_and_models_reference_match_config():
    for doc in ("README.md", "references/models.md"):
        text = (SKILL_DIR / doc).read_text()
        for name, role in CONFIG["roles"].items():
            row = next((l for l in text.splitlines() if l.startswith(f"| `{name}` |")), None)
            assert row is not None, f"{name} missing from {doc}"
            assert f"`{role['model']}`" in row, (doc, name)


def test_gate_commands_named_in_skill_exist_in_script():
    script = (SKILL_DIR / "scripts" / "h2o_gate.py").read_text()
    for command in set(re.findall(r"h2o_gate\.py (\w[\w-]*)", SKILL)):
        assert f'add_parser("{command}"' in script, command


# Split so this file never matches itself.
_CORP_PATTERNS = [re.compile("".join(p), re.I) for p in (
    ("-l", "-tf-"), ("launch", "-candidate"), ("team", "food"), ("3p", "-wtu"),
    ("gemini-pro", "-coordinator"), ("jet", "ski"), (r"(?<![\w-])opus-5", r"\.5"),
)]


def test_no_corp_catalogue_identifiers_in_skill():
    """The repo is public: only public catalogue IDs may appear."""
    for path in sorted(SKILL_DIR.rglob("*")):
        if path.is_file() and path.suffix in {".md", ".json", ".py"} and "__pycache__" not in path.parts:
            text = path.read_text()
            for pattern in _CORP_PATTERNS:
                assert not pattern.search(text), (path.name, pattern.pattern)


def test_skill_declares_its_own_model_ruleset():
    assert "own model ruleset" in SKILL
    assert "own model ruleset" in (SKILL_DIR / "references" / "models.md").read_text()
