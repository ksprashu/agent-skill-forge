# Copyright 2026 Agent Skill Forge Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for skills/handoff/scripts/handoff_ops.py (Engineering Standard T1-T6, V1-V5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "handoff_ops.py"
FIXTURES = SKILL_DIR / "fixtures"

sys.path.insert(0, str(SKILL_DIR / "scripts"))
import handoff_ops  # noqa: E402


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        shell=False,
    )


def _init_git_repo(repo: Path, files: dict[str, str], commit_msg: str = "init") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True, shell=False)
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, shell=False)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            commit_msg,
        ],
        cwd=str(repo),
        check=True,
        shell=False,
    )


class TestKnownFixtures:
    """Verifier contract V1, V2, CWE-22 confinement, and T4 negative tests."""

    def test_known_good_fixture_validates_zero(self) -> None:
        res = _run_cli(
            "validate",
            "--state",
            str(FIXTURES / "known_good" / "state.json"),
            "--manifest",
            str(FIXTURES / "known_good" / "manifest.json"),
        )
        assert res.returncode == 0, res.stderr + res.stdout
        assert "did not judge" in res.stdout.lower()

    def test_known_bad_secret_leak_rejected_nonzero(self) -> None:
        res = _run_cli(
            "validate",
            "--state",
            str(FIXTURES / "known_bad" / "secret_leak_state.json"),
        )
        assert res.returncode != 0
        combined = (res.stdout + res.stderr).lower()
        assert "secret" in combined or "token" in combined

    def test_known_bad_hollow_state_rejected_nonzero(self) -> None:
        res = _run_cli(
            "validate",
            "--state",
            str(FIXTURES / "known_bad" / "hollow_state.json"),
        )
        assert res.returncode != 0
        combined = (res.stdout + res.stderr).lower()
        assert "title" in combined
        assert "mission" in combined
        assert "next_actions" in combined

    def test_known_bad_broken_path_rejected_when_check_paths_enabled(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "sample-repo"
        repo.mkdir()
        manifest = {
            "schema_version": 1,
            "captured_at": "2026-11-09T09:00:00Z",
            "primary_workspace": "sample-repo",
            "workspaces": [
                {
                    "name": "sample-repo",
                    "path": str(repo),
                    "is_git": False,
                    "branch": None,
                    "head_sha": None,
                    "head_subject": None,
                    "recent_commits": [],
                    "dirty_files": [],
                    "dirty_total": 0,
                    "watched_digests": {},
                }
            ],
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        res = _run_cli(
            "validate",
            "--state",
            str(FIXTURES / "known_bad" / "broken_path_state.json"),
            "--manifest",
            str(manifest_path),
            "--check-paths",
        )
        assert res.returncode != 0
        assert "does_not_exist_anywhere.md" in (res.stdout + res.stderr)

    def test_check_paths_rejects_traversal_and_outside_paths(self, tmp_path: Path) -> None:
        outside_secret = tmp_path / "outside.txt"
        outside_secret.write_text("outside workspace\n", encoding="utf-8")
        repo = tmp_path / "confined-repo"
        repo.mkdir()
        (repo / "inside.md").write_text("ok\n", encoding="utf-8")

        manifest = {
            "schema_version": 1,
            "captured_at": "2026-11-09T09:00:00Z",
            "primary_workspace": "confined-repo",
            "workspaces": [
                {
                    "name": "confined-repo",
                    "path": str(repo),
                    "is_git": False,
                    "branch": None,
                    "head_sha": None,
                    "head_subject": None,
                    "recent_commits": [],
                    "dirty_files": [],
                    "dirty_total": 0,
                    "watched_digests": {},
                }
            ],
        }
        mp = repo / "manifest.json"
        mp.write_text(json.dumps(manifest), encoding="utf-8")

        for bad_ref in ("../outside.txt", str(outside_secret)):
            st = json.loads((FIXTURES / "known_good" / "state.json").read_text(encoding="utf-8"))
            st["active_focus"]["active_files"] = [bad_ref]
            st["completed"] = []
            sp = repo / "state.json"
            sp.write_text(json.dumps(st), encoding="utf-8")
            res = _run_cli("validate", "--state", str(sp), "--manifest", str(mp), "--check-paths")
            assert res.returncode != 0, f"Should have rejected escaping path: {bad_ref}"
            assert "escapes captured workspaces" in (res.stdout + res.stderr)


class TestDifferentiation:
    """T1: Two opposite handoff states must produce completely distinct outputs."""

    def test_opposite_inputs_produce_distinct_artifacts(self, tmp_path: Path) -> None:
        repo_a = tmp_path / "alpha"
        repo_b = tmp_path / "omega"
        _init_git_repo(repo_a, {"src/audio.py": "print('audio')\n"}, "feat: audio dsp")
        _init_git_repo(repo_b, {"docs/guide.md": "# Guide\n"}, "docs: initial guide")

        state_a = {
            "schema_version": 1,
            "title": "Alpha Audio DSP Pipeline Handoff",
            "mission": "Finish 5-band ReaEQ linear gain automation.",
            "active_focus": {
                "summary": "Implementing db_to_linear_gain in src/audio.py.",
                "primary_workspace": "alpha",
                "active_files": ["src/audio.py"],
            },
            "completed": [
                {
                    "item": "Scaffolded audio module",
                    "artifacts": ["src/audio.py"],
                    "verification": "python3 src/audio.py",
                }
            ],
            "locked_decisions": [
                {
                    "decision": "Convert decibels via 10^(dB/20)",
                    "rationale": "ReaEQ C++ API expects linear voltage.",
                }
            ],
            "next_actions": [
                {
                    "step": "Add unit test for -6 dB cut",
                    "command_or_prompt": "pytest tests/test_audio.py",
                    "expected_outcome": "0.501187 linear ratio verified",
                }
            ],
            "open_questions": ["Should high-pass default to 90 Hz or 95 Hz?"],
            "suggested_skills": [{"skill": "test", "why": "Run TDD prove-it loop"}],
            "resume_verification": ["python3 src/audio.py"],
        }

        state_b = {
            "schema_version": 1,
            "title": "Omega Documentation Series Handoff",
            "mission": "Publish 8-part tutorial series and HTML readout.",
            "active_focus": {
                "summary": "Polishing docs/guide.md readability.",
                "primary_workspace": "omega",
                "active_files": ["docs/guide.md"],
            },
            "completed": [
                {
                    "item": "Drafted guide header",
                    "artifacts": ["docs/guide.md"],
                    "verification": "wc -l docs/guide.md",
                }
            ],
            "locked_decisions": [
                {
                    "decision": "Use Commonwealth spelling and zero em-dashes",
                    "rationale": "Matches author voice register.",
                }
            ],
            "next_actions": [
                {
                    "step": "Compile standalone HTML report",
                    "command_or_prompt": "Build report in reports/guide.html",
                    "expected_outcome": "Self-contained HTML saved",
                }
            ],
            "open_questions": [],
            "suggested_skills": [{"skill": "atelier", "why": "Design HTML deliverable"}],
            "resume_verification": ["git status -sb"],
        }

        outputs: list[dict[str, str]] = []
        for repo, st in ((repo_a, state_a), (repo_b, state_b)):
            assert _run_cli("capture", "--root", str(repo)).returncode == 0
            st_path = repo / ".handoff" / "state.json"
            st_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
            assert (
                _run_cli(
                    "render",
                    "--manifest",
                    str(repo / ".handoff" / "manifest.json"),
                    "--state",
                    str(st_path),
                    "--out",
                    str(repo / ".handoff" / "HANDOFF.md"),
                ).returncode
                == 0
            )
            assert _run_cli("arm", "--root", str(repo)).returncode == 0
            status_res = _run_cli("status", "--root", str(repo), "--json")
            assert status_res.returncode == 0
            outputs.append(
                {
                    "handoff_md": (repo / ".handoff" / "HANDOFF.md").read_text(encoding="utf-8"),
                    "agents_md": (repo / "AGENTS.md").read_text(encoding="utf-8"),
                    "cursor_mdc": (
                        repo / ".cursor" / "rules" / "00-active-handoff.mdc"
                    ).read_text(encoding="utf-8"),
                    "status_json": status_res.stdout,
                }
            )

        for key in outputs[0]:
            assert outputs[0][key] != outputs[1][key], f"{key} did not vary with input"


class TestSecretRedactionAtCapture:
    """S8 & S9: Capture redacts secrets immediately and emits zero judgement scores."""

    def test_capture_redacts_tokens_and_emits_no_scores(self, tmp_path: Path) -> None:
        repo = tmp_path / "sec-repo"
        fake_openai = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4"
        fake_google = "AIza" + "SyD1234567890abcdefghijklmnopqrstuv"
        fake_github = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
        _init_git_repo(
            repo,
            {"notes.txt": "clean\n"},
            commit_msg=f"debug key {fake_openai} and {fake_google} and {fake_github}",
        )

        res = _run_cli("capture", "--root", str(repo))
        assert res.returncode == 0, res.stderr
        raw_manifest = (repo / ".handoff" / "manifest.json").read_text(encoding="utf-8")

        assert fake_openai not in raw_manifest
        assert fake_google not in raw_manifest
        assert fake_github not in raw_manifest
        assert "[REDACTED" in raw_manifest

        parsed = json.loads(raw_manifest)
        forbidden_judgement_keys = {"score", "grade", "rating", "quality", "band"}
        assert not (forbidden_judgement_keys & set(parsed.keys()))


class TestEndToEndLifecycleAndDrift:
    """T3 & T5: Automatic porcelain capture, idempotent re-arm, branch/tree drift, and byte-exact disarm."""

    def test_full_lifecycle_idempotent_rearm_drift_and_byte_exact_disarm(
        self, tmp_path: Path
    ) -> None:
        primary = tmp_path / "content-workspace"
        sibling = tmp_path / "toolchain-repo"

        orig_primary_agents = "# Primary AGENTS\n\nKeep under 200 lines.\n"
        orig_primary_claude = "# Claude Instructions\n\nFollow AGENTS.md.\n"
        orig_sibling_agents = "# Toolchain AGENTS\n\nRun pytest before merge.\n"

        _init_git_repo(
            primary,
            {
                "AGENTS.md": orig_primary_agents,
                "CLAUDE.md": orig_primary_claude,
                "blogs/01-post.md": "# Draft v1\n\nInitial paragraph.\n",
            },
            commit_msg="docs: add initial blog draft",
        )
        _init_git_repo(
            sibling,
            {
                "AGENTS.md": orig_sibling_agents,
                "skills/sound/session.py": "def gain():\n    return 1.0\n",
            },
            commit_msg="feat: sound session helper",
        )

        # Pre-existing local Claude setting that disarm MUST preserve
        claude_dir = primary / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Read"]}}, indent=2),
            encoding="utf-8",
        )

        # Unstaged modification BEFORE capture — NO explicit --watch-file passed!
        # Verifies R-001/R-005: leading space in ` M blogs/01-post.md` is preserved.
        (primary / "blogs" / "01-post.md").write_text(
            "# Draft v2\n\nUpdated paragraph before handoff.\n", encoding="utf-8"
        )

        cap = _run_cli("capture", "--root", str(primary), "--extra-repo", str(sibling))
        assert cap.returncode == 0, cap.stderr

        manifest_data = json.loads(
            (primary / ".handoff" / "manifest.json").read_text(encoding="utf-8")
        )
        ws0 = manifest_data["workspaces"][0]
        assert ws0["dirty_files"] == [{"status": "M", "path": "blogs/01-post.md"}]
        assert "blogs/01-post.md" in ws0["watched_digests"]

        state = {
            "schema_version": 1,
            "title": "Cross-Repo Content & Toolchain Handoff",
            "mission": "Resume Part 01 blog review and launch Part 02.",
            "active_focus": {
                "summary": "Reviewing blogs/01-post.md paired with skills/sound/session.py.",
                "primary_workspace": "content-workspace",
                "active_files": ["blogs/01-post.md", "skills/sound/session.py"],
            },
            "completed": [
                {
                    "item": "Implemented session helper and drafted blog v2",
                    "artifacts": ["blogs/01-post.md", "skills/sound/session.py"],
                    "verification": "Validated frontmatter and unit tests",
                }
            ],
            "locked_decisions": [
                {
                    "decision": "Never use legacy idx.dev links",
                    "rationale": "Canonical URL is https://antigravity.google",
                }
            ],
            "next_actions": [
                {
                    "step": "Build companion video outline",
                    "command_or_prompt": "Create blogs/01-video-script.md",
                    "expected_outcome": "Chaptered video script ready",
                }
            ],
            "open_questions": [],
            "suggested_skills": [{"skill": "voice-register", "why": "R3 blog voice"}],
            "resume_verification": ["git status -sb"],
        }
        state_path = primary / ".handoff" / "state.json"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        val = _run_cli(
            "validate",
            "--state",
            str(state_path),
            "--manifest",
            str(primary / ".handoff" / "manifest.json"),
            "--check-paths",
        )
        assert val.returncode == 0, val.stderr + val.stdout

        ren = _run_cli(
            "render",
            "--manifest",
            str(primary / ".handoff" / "manifest.json"),
            "--state",
            str(state_path),
            "--out",
            str(primary / ".handoff" / "HANDOFF.md"),
            "--check-paths",
        )
        assert ren.returncode == 0, ren.stderr

        # Arm TWICE + re-run capture while armed (verifies R-002 idempotency!)
        assert _run_cli("arm", "--root", str(primary), "--link-repo", str(sibling)).returncode == 0
        assert _run_cli("capture", "--root", str(primary), "--extra-repo", str(sibling)).returncode == 0
        assert _run_cli("arm", "--root", str(primary), "--link-repo", str(sibling)).returncode == 0

        # Verify beacons across all harnesses (sibling had no CLAUDE.md initially -> created & tracked!)
        assert handoff_ops.BEACON_START in (primary / "AGENTS.md").read_text(encoding="utf-8")
        assert handoff_ops.BEACON_START in (primary / "CLAUDE.md").read_text(encoding="utf-8")
        assert handoff_ops.BEACON_START in (sibling / "AGENTS.md").read_text(encoding="utf-8")
        assert (sibling / "CLAUDE.md").exists()
        assert "@.handoff/HANDOFF.md" in (sibling / "CLAUDE.md").read_text(encoding="utf-8")
        assert (primary / ".cursor" / "rules" / "00-active-handoff.mdc").exists()

        claude_settings = json.loads(
            (primary / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        assert claude_settings["permissions"] == {"allow": ["Read"]}
        assert "SessionStart" in claude_settings["hooks"]

        # Verify status is clean right after re-arming
        st_clean = json.loads(
            _run_cli("status", "--root", str(primary), "--json").stdout
        )
        assert st_clean["active"] is True
        assert st_clean["armed"] is True
        assert st_clean["drift_detected"] is False, st_clean["drifted_items"]

        # 1. Modify blogs/01-post.md AND create a brand-new untracked file AND switch git branch in sibling (R-003)
        (primary / "blogs" / "01-post.md").write_text(
            "# Draft v3\n\nOut-of-band edit after handoff!\n", encoding="utf-8"
        )
        (primary / "blogs" / "unexpected.md").write_text("new file\n", encoding="utf-8")
        subprocess.run(
            ["git", "checkout", "-qb", "feat/new-branch"],
            cwd=str(sibling),
            check=True,
            shell=False,
        )

        st_drift = json.loads(
            _run_cli("status", "--root", str(primary), "--json").stdout
        )
        assert st_drift["drift_detected"] is True
        joined_drift = "\n".join(st_drift["drifted_items"])
        assert "01-post.md" in joined_drift
        assert "unexpected.md" in joined_drift
        assert "feat/new-branch" in joined_drift

        # Disarm with --archive and prove byte-for-byte restoration even after double-arm!
        dis = _run_cli("disarm", "--root", str(primary), "--archive")
        assert dis.returncode == 0, dis.stderr

        assert (primary / "AGENTS.md").read_text(encoding="utf-8") == orig_primary_agents
        assert (primary / "CLAUDE.md").read_text(encoding="utf-8") == orig_primary_claude
        assert (sibling / "AGENTS.md").read_text(encoding="utf-8") == orig_sibling_agents
        assert not (sibling / "CLAUDE.md").exists()
        assert not (sibling / ".claude" / "settings.local.json").exists()
        assert not (primary / ".cursor" / "rules" / "00-active-handoff.mdc").exists()

        restored_settings = json.loads(
            (primary / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        assert restored_settings == {"permissions": {"allow": ["Read"]}}
        assert not (primary / ".handoff" / "HANDOFF.md").exists()
        archives = list((primary / ".handoff" / "archive").iterdir())
        assert len(archives) == 1
        assert (archives[0] / "HANDOFF.md").exists()

    def test_cmd_arm_rejects_secret_leaking_state(self, tmp_path: Path) -> None:
        repo = tmp_path / "bad-arm"
        _init_git_repo(repo, {"app.py": "x = 1\n"}, "init")
        assert _run_cli("capture", "--root", str(repo)).returncode == 0
        (repo / ".handoff" / "HANDOFF.md").write_text("# stub\n", encoding="utf-8")
        (repo / ".handoff" / "state.json").write_text(
            (FIXTURES / "known_bad" / "secret_leak_state.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        res = _run_cli("arm", "--root", str(repo))
        assert res.returncode != 0
        assert not (repo / "AGENTS.md").exists()


class TestCLIHelpAndContract:
    """S6: Every subcommand supports --help cleanly."""

    def test_all_subcommands_expose_help(self) -> None:
        for sub in ([], ["capture"], ["validate"], ["render"], ["arm"], ["status"], ["disarm"]):
            res = _run_cli(*sub, "--help")
            assert res.returncode == 0, f"Failed --help for {sub}: {res.stderr}"

    def test_arm_on_untracked_or_dirty_agents_md_causes_zero_false_drift(self, tmp_path: Path) -> None:
        repo = tmp_path / "dirty-agents-repo"
        _init_git_repo(repo, {"README.md": "# Hi\n"}, "init")
        (repo / "AGENTS.md").write_text("# Workspace Rules\n\nRule 1.\n", encoding="utf-8")

        assert _run_cli("capture", "--root", str(repo)).returncode == 0
        st = json.loads((FIXTURES / "known_good" / "state.json").read_text(encoding="utf-8"))
        st["active_focus"]["primary_workspace"] = "dirty-agents-repo"
        st["active_focus"]["active_files"] = ["README.md"]
        st["completed"][0]["artifacts"] = ["README.md"]
        st_path = repo / ".handoff" / "state.json"
        st_path.write_text(json.dumps(st), encoding="utf-8")

        assert (
            _run_cli(
                "render",
                "--manifest",
                str(repo / ".handoff" / "manifest.json"),
                "--state",
                str(st_path),
                "--out",
                str(repo / ".handoff" / "HANDOFF.md"),
            ).returncode
            == 0
        )
        assert _run_cli("arm", "--root", str(repo)).returncode == 0
        status = json.loads(_run_cli("status", "--root", str(repo), "--json").stdout)
        assert status["drift_detected"] is False, status["drifted_items"]
