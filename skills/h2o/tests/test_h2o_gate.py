"""Tests for scripts/h2o_gate.py: differentiation (T1), derived limits (T3) and negatives (T4)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "h2o_gate.py"
CONFIG = json.loads((SKILL_DIR / "swarm.config.json").read_text())
CAP = CONFIG["loop_policy"]["max_not_good_per_gate"]


def run(*args, stdin=None):
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, input=stdin, check=False)
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    return proc.returncode, payload


GOOD = """@coordinator [done] VERDICT: GOOD
Evidence:
$ python3 -m pytest -q
42 passed in 1.2s
Findings:
None.
"""
NOT_GOOD = """@coordinator [done] VERDICT: NOT GOOD
Evidence: `pytest -q` -> 1 failed, src/app.py:40 returns None on empty input
Findings:
1. High: empty input crashes the parser; return [] instead.
"""
DESIGN = NOT_GOOD.replace("VERDICT: NOT GOOD", "VERDICT: NOT GOOD (DESIGN)")


# ------------------------------------------------------------------ verdict

@pytest.mark.parametrize("text,expected,code", [
    (GOOD, "GOOD", 0),
    (NOT_GOOD, "NOT_GOOD", 1),
    (DESIGN, "DESIGN", 1),
])
def test_verdicts_are_told_apart(text, expected, code):
    rc, out = run("verdict", "--file", "-", stdin=text)
    assert (rc, out["verdict"]) == (code, expected)


@pytest.mark.parametrize("text,reason", [
    ("@coordinator [done] VERDICT: GOOD\nEvidence: none\n", "no evidence"),
    ("@coordinator [done] VERDICT: GOOD\nEvidence: looks fine to me\n", "no evidence"),
    ("@coordinator [done] VERDICT: NOT GOOD\nEvidence: `pytest -q`\nFindings:\nbad\n", "numbered finding"),
    (GOOD + "\nVERDICT: NOT GOOD\n", "exactly one VERDICT"),
    ("All good, ship it.\n", "exactly one VERDICT"),
])
def test_malformed_verdicts_fail(text, reason):
    rc, out = run("verdict", "--file", "-", stdin=text)
    assert rc == 1
    assert out["verdict"] == "MALFORMED"
    assert any(reason in r for r in out["reasons"])


def test_verdict_missing_file_is_usage_error(tmp_path):
    rc, _ = run("verdict", "--file", tmp_path / "nope.md")
    assert rc == 2


# ------------------------------------------------------------------ freeze

@pytest.fixture
def frozen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CRITERIA.md").write_text("1. Parser returns [] on empty input\n")
    (tmp_path / "test_accept.py").write_text("def test_empty():\n    assert parse('') == []\n")
    state = tmp_path / "state"
    rc, _ = run("freeze", "--state-dir", state, "--file", "CRITERIA.md", "--file", "test_accept.py")
    assert rc == 0
    return tmp_path, state


def test_unchanged_frozen_files_pass(frozen):
    _, state = frozen
    assert run("check-frozen", "--state-dir", state)[0] == 0


def test_edited_frozen_file_fails(frozen):
    root, state = frozen
    (root / "test_accept.py").write_text("def test_empty():\n    pass\n")
    rc, out = run("check-frozen", "--state-dir", state)
    assert rc == 1 and out["changed"] == ["test_accept.py"]


def test_deleted_frozen_file_fails(frozen):
    root, state = frozen
    (root / "CRITERIA.md").unlink()
    rc, out = run("check-frozen", "--state-dir", state)
    assert rc == 1 and out["missing"] == ["CRITERIA.md"]


def test_refreeze_needs_force(frozen):
    _, state = frozen
    assert run("freeze", "--state-dir", state, "--file", "CRITERIA.md")[0] == 1
    assert run("freeze", "--state-dir", state, "--file", "CRITERIA.md", "--force")[0] == 0


def test_freeze_missing_file_is_usage_error(tmp_path):
    assert run("freeze", "--state-dir", tmp_path / "s", "--file", tmp_path / "nope.md")[0] == 2


# ------------------------------------------------------------------ record / grant

def record(state, gate, verdict):
    return run("record", "--state-dir", state, "--gate", gate, "--verdict", verdict)


def test_cap_comes_from_config_and_stops_the_loop(frozen):
    _, state = frozen
    for attempt in range(1, CAP):
        rc, out = record(state, "functional_review", "NOT_GOOD")
        assert rc == 0 and out["next_stage"] == "implement" and out["not_good"] == attempt
    rc, out = record(state, "functional_review", "NOT_GOOD")
    assert rc == 3 and out["next_stage"] == "ask_user"


def test_grant_reopens_the_gate(frozen):
    _, state = frozen
    for _ in range(CAP):
        record(state, "code_review", "NOT_GOOD")
    rc, out = run("grant", "--state-dir", state, "--gate", "code_review")
    assert rc == 0 and out["cap"] == CAP + CONFIG["loop_policy"]["continue_grants_attempts"]
    assert record(state, "code_review", "NOT_GOOD")[0] == 0


def test_design_verdict_charges_the_plan_gate(frozen):
    _, state = frozen
    rc, out = record(state, "security_review", "DESIGN")
    assert rc == 0
    assert out["charged_gate"] == CONFIG["loop_policy"]["design_defect_counts_against"]
    assert out["next_stage"] == "plan"


def test_routing_is_derived_from_config(frozen):
    _, state = frozen
    for stage in (s for s in CONFIG["stages"] if s.get("gate")):
        assert record(state, stage["id"], "GOOD")[1]["next_stage"] == stage["on_good"]


def test_good_is_never_charged(frozen):
    _, state = frozen
    for _ in range(CAP + 2):
        assert record(state, "plan_review", "GOOD")[0] == 0


def test_implementer_escalates_after_first_not_good(frozen):
    _, state = frozen
    impl = CONFIG["roles"]["implementer"]
    _, first = record(state, "functional_review", "NOT_GOOD")
    _, second = record(state, "code_review", "NOT_GOOD")
    assert first["escalate_implementer_to"] == impl["escalate_to"]
    assert second["escalate_implementer_to"] is None


def test_smaller_cap_in_config_is_honoured(frozen, tmp_path):
    _, state = frozen
    custom = dict(CONFIG, loop_policy=dict(CONFIG["loop_policy"], max_not_good_per_gate=1))
    path = tmp_path / "custom.json"
    path.write_text(json.dumps(custom))
    rc, _ = run("--config", path, "record", "--state-dir", state,
                "--gate", "plan_review", "--verdict", "NOT_GOOD")
    assert rc == 3


@pytest.mark.parametrize("gate,verdict", [("nope", "NOT_GOOD"), ("plan_review", "DESIGN")])
def test_bad_record_requests_are_usage_errors(frozen, gate, verdict):
    _, state = frozen
    assert record(state, gate, verdict)[0] == 2


def test_record_before_freeze_works_and_freeze_preserves_counts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "state"
    rc, out = record(state, "intent_review", "NOT_GOOD")
    assert rc == 0 and out["next_stage"] == "grill" and out["not_good"] == 1
    assert run("check-frozen", "--state-dir", state)[0] == 1

    (tmp_path / "CRITERIA.md").write_text("1. Done\n")
    assert run("freeze", "--state-dir", state, "--file", "CRITERIA.md")[0] == 0
    assert run("status", "--state-dir", state)[1]["not_good"]["intent_review"] == 1
    assert run("check-frozen", "--state-dir", state)[0] == 0


# ------------------------------------------------------------------ diff-guard

def guard(tmp_path, diff):
    path = tmp_path / "change.diff"
    path.write_text(diff)
    return run("diff-guard", "--diff-file", path)


def file_diff(path, body, header=""):
    return f"diff --git a/{path} b/{path}\n{header}--- a/{path}\n+++ b/{path}\n@@ -1,3 +1,3 @@\n{body}"


CLEAN = file_diff("src/parser.py", "-    return None\n+    return []\n") + file_diff(
    "tests/test_parser.py", "+    assert parse('') == []\n")


def test_clean_diff_passes(tmp_path):
    rc, out = guard(tmp_path, CLEAN)
    assert rc == 0 and out["violations"] == []


@pytest.mark.parametrize("diff,kind", [
    (file_diff("tests/test_parser.py", "+@pytest.mark.skip(reason='flaky')\n"), "added_skip"),
    (file_diff("web/app.test.ts", "+it.skip('renders', () => {})\n"), "added_skip"),
    (file_diff("src/parser.py", "+    value = load()  # type: ignore\n"), "added_suppression"),
    (file_diff("web/app.ts", "+// eslint-disable-next-line\n"), "added_suppression"),
    (file_diff("tests/test_parser.py", "-    assert parse('') == []\n+    parse('')\n"), "assertions_removed"),
    (file_diff("tests/test_parser.py", "-def test_x():\n-    assert True\n", "deleted file mode 100644\n"),
     "deleted_test_file"),
])
def test_weakened_tests_fail(tmp_path, diff, kind):
    rc, out = guard(tmp_path, diff)
    assert rc == 1
    assert kind in {v["kind"] for v in out["violations"]}


def test_removing_asserts_outside_tests_is_allowed(tmp_path):
    diff = file_diff("src/parser.py", "-    assert isinstance(x, str)\n+    check(x)\n")
    assert guard(tmp_path, diff)[0] == 0


def test_rewriting_an_assertion_is_allowed(tmp_path):
    diff = file_diff("tests/test_parser.py", "-    assert parse('') is None\n+    assert parse('') == []\n")
    assert guard(tmp_path, diff)[0] == 0


def test_diff_guard_missing_file_is_usage_error(tmp_path):
    assert run("diff-guard", "--diff-file", tmp_path / "nope.diff")[0] == 2
