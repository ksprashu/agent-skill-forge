#!/usr/bin/env python3
"""Test suite for skills/image-gen/scripts/image_gen.py.

Follows docs/ENGINEERING_STANDARD.md:
- V1/V2: Rejects every fixture in fixtures/known_bad/ and accepts fixtures/known_good/.
- T1: Differentiation across modes, styles, aspect ratios, and reference counts.
- T3: Derive-not-restate checks for quoted text literals and deprecated model constants.
- T4: Negative tests for corrupt/wrong-AR/undersized headers, partial/contradictory rubrics,
      deprecated models (exit 2), retry exhaustion (exit 1, no --output leak), edit_turn vs
      regenerate selection, and frozen spec.json immutability across retries.
- T5: Real subprocess CLI execution against binary fixtures and PATH-stubbed gemini-api.
- S6/T6: --help flag parity with SKILL.md and shared constant contract verification.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "image_gen.py"
FIXTURES_DIR = SKILL_DIR / "fixtures"
KNOWN_GOOD_DIR = FIXTURES_DIR / "known_good"
KNOWN_BAD_DIR = FIXTURES_DIR / "known_bad"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import image_gen  # noqa: E402


@dataclass
class StubProcResult:
    returncode: int
    stdout: str
    stderr: str = ""


class FakeGeminiRunner:
    """Deterministic callable runner recording every subprocess argv vector."""

    def __init__(self, handlers: list[Any] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._handlers: list[Any] = list(handlers or [])

    def add(self, handler: Any) -> None:
        self._handlers.append(handler)

    def __call__(self, cmd: Sequence[str], *, timeout: int = 180) -> StubProcResult:
        argv = [str(part) for part in cmd]
        self.calls.append(argv)
        if not self._handlers:
            raise AssertionError(f"Unexpected command invocation: {argv}")
        handler = self._handlers.pop(0)
        if callable(handler):
            return handler(argv, timeout)
        return handler


def _wrap_generate_json(payload: dict[str, Any], response_id: str = "gen_judge_1") -> str:
    return json.dumps(
        {
            "id": response_id,
            "status": "completed",
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                }
            ],
            "usage": {"input_tokens": 120, "output_tokens": 64},
        }
    )


def _all_passing_verdict_for(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall_pass": True,
        "criteria_results": [
            {
                "id": item["id"],
                "passed": True,
                "observed_evidence": f"Verified {item['id']} visibly satisfied in candidate image.",
                "fix_instruction": "",
            }
            for item in spec["acceptance_criteria"]
        ],
        "remediation_mode": "edit_turn",
        "edit_delta_prompt": "",
        "regenerated_prompt": "",
    }


# ---------------------------------------------------------------------------
# V1 & V2: Mechanical binary header & dimension/AR verification on fixtures
# ---------------------------------------------------------------------------


def test_mechanical_accepts_all_known_good_binary_headers() -> None:
    png_res = image_gen.verify_image_mechanical(
        KNOWN_GOOD_DIR / "valid_16x9_1344x768.png",
        target_ar="16:9",
        target_size="1K",
    )
    assert png_res["passed"] is True
    assert png_res["mime_type"] == "image/png"
    assert (png_res["width"], png_res["height"]) == (1344, 768)
    assert png_res["errors"] == []

    comic_res = image_gen.verify_image_mechanical(
        KNOWN_GOOD_DIR / "valid_comic_2k_2048x2048.png",
        target_ar="1:1",
        target_size="2K",
    )
    assert comic_res["passed"] is True
    assert (comic_res["width"], comic_res["height"]) == (2048, 2048)

    jpg_res = image_gen.verify_image_mechanical(
        KNOWN_GOOD_DIR / "valid_4x3_1152x864.jpg",
        target_ar="4:3",
        target_size="1K",
    )
    assert jpg_res["passed"] is True
    assert jpg_res["mime_type"] == "image/jpeg"
    assert (jpg_res["width"], jpg_res["height"]) == (1152, 864)

    webp_vp8x = image_gen.verify_image_mechanical(
        KNOWN_GOOD_DIR / "valid_16x9_vp8x_1600x900.webp",
        target_ar="16:9",
        target_size="2K",
    )
    assert webp_vp8x["passed"] is True
    assert webp_vp8x["mime_type"] == "image/webp"
    assert (webp_vp8x["width"], webp_vp8x["height"]) == (1600, 900)

    webp_vp8 = image_gen.verify_image_mechanical(
        KNOWN_GOOD_DIR / "valid_1x1_vp8_1024x1024.webp",
        target_ar="1:1",
        target_size="1K",
    )
    assert webp_vp8["passed"] is True
    assert webp_vp8["mime_type"] == "image/webp"
    assert (webp_vp8["width"], webp_vp8["height"]) == (1024, 1024)


def test_mechanical_rejects_known_bad_corrupt_wrong_ar_and_undersized() -> None:
    corrupt_png = image_gen.verify_image_mechanical(
        KNOWN_BAD_DIR / "corrupt_header.png",
        target_ar="16:9",
        target_size="1K",
    )
    assert corrupt_png["passed"] is False
    assert any("PNG" in err or "IHDR" in err for err in corrupt_png["errors"])

    corrupt_webp = image_gen.verify_image_mechanical(
        KNOWN_BAD_DIR / "corrupt_truncated.webp",
        target_ar="16:9",
        target_size="1K",
    )
    assert corrupt_webp["passed"] is False
    assert any("WebP" in err or "RIFF" in err or "truncated" in err.lower() for err in corrupt_webp["errors"])

    wrong_ar = image_gen.verify_image_mechanical(
        KNOWN_BAD_DIR / "wrong_ar_1x1_1024x1024.png",
        target_ar="16:9",
        target_size="1K",
    )
    assert wrong_ar["passed"] is False
    assert (wrong_ar["width"], wrong_ar["height"]) == (1024, 1024)
    assert any("aspect ratio" in err.lower() for err in wrong_ar["errors"])

    undersized = image_gen.verify_image_mechanical(
        KNOWN_BAD_DIR / "undersized_comic_grid_1024x1024.png",
        target_ar="1:1",
        target_size="2K",
    )
    assert undersized["passed"] is False
    assert any("1500" in err for err in undersized["errors"])


# ---------------------------------------------------------------------------
# V1 & V2 & S9: Rubric provenance & consistency validator on fixtures
# ---------------------------------------------------------------------------


def test_rubric_validator_accepts_known_good_and_rejects_known_bad() -> None:
    spec = json.loads((KNOWN_GOOD_DIR / "sample_spec_16x9.json").read_text(encoding="utf-8"))
    good_rubric = json.loads((KNOWN_GOOD_DIR / "passing_rubric.json").read_text(encoding="utf-8"))
    good_eval = image_gen.validate_rubric_verdict(good_rubric, spec)
    assert good_eval["passed"] is True
    assert good_eval["pass_ratio"] == 1.0
    assert good_eval["contradiction_detected"] is False
    assert good_eval["failed_ids"] == []

    partial_rubric = json.loads((KNOWN_BAD_DIR / "partial_fail_rubric.json").read_text(encoding="utf-8"))
    partial_eval = image_gen.validate_rubric_verdict(partial_rubric, spec)
    assert partial_eval["passed"] is False
    assert partial_eval["pass_ratio"] == 0.75
    assert partial_eval["failed_ids"] == ["AC-3"]
    assert image_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation=partial_eval,
        response_id="v1_resp_1",
    ) == "edit_turn"

    major_rubric = json.loads((KNOWN_BAD_DIR / "major_fail_rubric.json").read_text(encoding="utf-8"))
    major_eval = image_gen.validate_rubric_verdict(major_rubric, spec)
    assert major_eval["passed"] is False
    assert major_eval["pass_ratio"] == 0.25
    assert image_gen.select_remediation_mode(
        mechanical_passed=True,
        rubric_validation=major_eval,
        response_id="v1_resp_1",
    ) == "regenerate"

    contradictory = json.loads((KNOWN_BAD_DIR / "contradictory_rubric.json").read_text(encoding="utf-8"))
    contra_eval = image_gen.validate_rubric_verdict(contradictory, spec)
    assert contra_eval["passed"] is False
    assert contra_eval["contradiction_detected"] is True
    assert contra_eval["failed_ids"] == ["AC-2"]

    missing_ac = json.loads((KNOWN_BAD_DIR / "missing_ac_rubric.json").read_text(encoding="utf-8"))
    missing_eval = image_gen.validate_rubric_verdict(missing_ac, spec)
    assert missing_eval["passed"] is False
    assert any("AC-4" in err for err in missing_eval["errors"])


# ---------------------------------------------------------------------------
# T1: Differentiation across modes, aspect ratios, styles, and references
# ---------------------------------------------------------------------------


def test_t1_differentiation_across_modes_and_cli_vectors() -> None:
    spec_comic = image_gen.compile_spec(
        prompt='2x2 comic strip about debugging with speech bubbles "Ship it!" and "Wait—check CI!"',
        mode="comic-grid",
        style="gritty noir b&w ink",
        aspect_ratio="1:1",
        image_size="1K",
        references=[{"role": "char", "path": "hero_sheet.png"}],
    )
    spec_diagram = image_gen.compile_spec(
        prompt="Orthographic cloud service mesh architecture flow",
        mode="diagram",
        style="isometric dark-mode vector",
        aspect_ratio="21:9",
        image_size="1K",
        references=[],
    )
    spec_single = image_gen.compile_spec(
        prompt="Minimalist ceramic tea cup on linen cloth",
        mode="single",
        style="watercolour botanical",
        aspect_ratio="4:5",
        image_size="1K",
        references=[],
    )

    # Every compiled output artifact field differs meaningfully across inputs
    assert spec_comic["mode"] == "comic-grid"
    assert spec_diagram["mode"] == "diagram"
    assert spec_single["mode"] == "single"

    # Comic-grid auto-upgrades 1K -> 2K; single without dense text stays 1K
    assert spec_comic["image_size"] == "2K"
    assert spec_single["image_size"] == "1K"

    assert spec_comic["compiled_prompt"] != spec_diagram["compiled_prompt"]
    assert spec_diagram["compiled_prompt"] != spec_single["compiled_prompt"]
    assert spec_comic["implicit_constraints"] != spec_diagram["implicit_constraints"]
    assert spec_diagram["implicit_constraints"] != spec_single["implicit_constraints"]
    assert spec_comic["acceptance_criteria"] != spec_diagram["acceptance_criteria"]

    chain_comic = image_gen.build_image_model_chain(
        None,
        mode=spec_comic["mode"],
        has_references=True,
        has_quoted_text=True,
        multi_panel=True,
    )
    chain_single = image_gen.build_image_model_chain(
        None,
        mode=spec_single["mode"],
        has_references=False,
        has_quoted_text=False,
        multi_panel=False,
    )
    assert chain_comic == ["gemini-3-pro-image", "gemini-nano-banana-2.1"]
    assert chain_single == [
        "gemini-nano-banana-2.1",
        "gemini-3-pro-image",
        "gemini-3.1-flash-lite-image",
    ]

    cmd_comic = image_gen.build_image_cli_command(
        prompt=spec_comic["compiled_prompt"],
        model=chain_comic[0],
        aspect_ratio=spec_comic["aspect_ratio"],
        image_size=spec_comic["image_size"],
        out_path=Path("comic.png"),
        references=["hero_sheet.png"],
        previous_interaction_id=None,
        mode=spec_comic["mode"],
        has_quoted_text=True,
        target_mime="image/png",
    )
    cmd_single = image_gen.build_image_cli_command(
        prompt=spec_single["compiled_prompt"],
        model=chain_single[0],
        aspect_ratio=spec_single["aspect_ratio"],
        image_size=spec_single["image_size"],
        out_path=Path("cup.webp"),
        references=[],
        previous_interaction_id=None,
        mode=spec_single["mode"],
        has_quoted_text=False,
        target_mime="image/webp",
    )
    assert cmd_comic != cmd_single
    body_comic = json.loads(cmd_comic[cmd_comic.index("--body") + 1])
    body_single = json.loads(cmd_single[cmd_single.index("--body") + 1])
    assert body_comic["generation_config"]["thinking_level"] == "high"
    assert "generation_config" not in body_single
    assert body_comic["response_format"]["mime_type"] == "image/png"
    assert body_single["response_format"]["mime_type"] == "image/webp"


# ---------------------------------------------------------------------------
# T3: Derive, don't restate (quoted literals, prompt expansion guard, constants)
# ---------------------------------------------------------------------------


def test_t3_quoted_literals_propagate_and_expansion_guard_blocks_drops() -> None:
    raw = 'Diagram with boxes "Ingress Router" and \'Policy Engine\' showing don\'t-trust boundary'
    literals = image_gen.extract_quoted_literals(raw)
    assert literals == ["Ingress Router", "Policy Engine"]

    spec = image_gen.compile_spec(
        prompt=raw,
        mode="auto",
        style=None,
        aspect_ratio="16:9",
        image_size="1K",
        references=[],
    )
    assert spec["mode"] == "diagram"
    assert spec["image_size"] == "2K"  # 2 quoted literals -> dense text floor
    assert spec["explicit_constraints"]["quoted_literals"] == ["Ingress Router", "Policy Engine"]
    text_acs = [ac for ac in spec["acceptance_criteria"] if ac["category"] == "text"]
    assert len(text_acs) == 1
    assert "Ingress Router" in text_acs[0]["requirement"]
    assert "Policy Engine" in text_acs[0]["requirement"]

    ok_good, missing_good = image_gen.validate_expanded_prompt(
        raw,
        'Detailed dark-mode diagram featuring "Ingress Router" wired to "Policy Engine" across zero-trust boundary.',
        literals,
    )
    assert ok_good is True
    assert missing_good == []

    ok_bad, missing_bad = image_gen.validate_expanded_prompt(
        raw,
        'Detailed dark-mode diagram featuring "Ingress Router" wired to an auth box.',
        literals,
    )
    assert ok_bad is False
    assert missing_bad == ["Policy Engine"]


def test_t6_shared_constants_and_deprecated_model_blocklist() -> None:
    assert image_gen.VERIFIER_MODEL_CHAIN == (
        "gemini-4-argon",
        "gemini-4-carbon",
        "gemini-3.8-flash",
    )
    assert image_gen.DEPRECATED_MODEL_PREFIXES == (
        "gemini-1.5",
        "gemini-2.0",
        "gemini-2.5",
        "gemini-3.1-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-3.1-pro",
        "imagen-",
        "veo-2",
        "veo-3.1",
        "gemini-omni-flash-preview",
    )
    assert len(image_gen.SUPPORTED_ASPECT_RATIOS) == 14
    for ratio in ("1:1", "16:9", "9:16", "21:9", "1:4", "4:1", "1:8", "8:1"):
        assert ratio in image_gen.SUPPORTED_ASPECT_RATIOS

    # Active lite backup must be permitted, while shut-down flash-image and preview IDs exit 2
    image_gen.validate_model_id("gemini-3.1-flash-lite-image")
    image_gen.validate_model_id("gemini-nano-banana-2.1")
    image_gen.validate_model_id("gemini-3-pro-image")


# ---------------------------------------------------------------------------
# T4: Negative CLI tests (deprecated models exit 2, >14 refs exit 2, retries)
# ---------------------------------------------------------------------------


def test_t4_deprecated_models_and_invalid_reference_count_exit_two(tmp_path: Path) -> None:
    runner = FakeGeminiRunner()
    for bad_model in (
        "gemini-3.1-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-2.5-flash-image",
        "imagen-3.0-generate-002",
        "veo-3.1-generate-preview",
    ):
        rc = image_gen.main(
            ["--prompt", "A lighthouse", "--model", bad_model, "--dry-run"],
            runner=runner,
        )
        assert rc == 2
        assert runner.calls == []

    rc_bad_verifier = image_gen.main(
        ["--prompt", "A lighthouse", "--verifier-model", "gemini-3.1-pro-high", "--dry-run"],
        runner=runner,
    )
    assert rc_bad_verifier == 2

    # >14 references must exit 2
    refs_args: list[str] = []
    for idx in range(15):
        p = tmp_path / f"ref_{idx}.png"
        p.write_bytes((KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes())
        refs_args.extend(["-r", str(p)])
    rc_too_many = image_gen.main(
        ["--prompt", "Group scene", *refs_args, "--dry-run"],
        runner=runner,
    )
    assert rc_too_many == 2


def test_dual_mode_retry_uses_edit_turn_on_75pct_pass_and_keeps_frozen_spec(tmp_path: Path) -> None:
    out_file = tmp_path / "arch.png"
    good_png_bytes = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    judge_prompts_seen: list[str] = []

    def handle_attempt_1_gen(argv: list[str], _timeout: int) -> StubProcResult:
        assert argv[:2] == ["gemini-api", "image"]
        assert "--previous-interaction-id" not in argv
        staged_out = Path(argv[argv.index("--out") + 1])
        staged_out.write_bytes(good_png_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged_out),
                    "size_bytes": len(good_png_bytes),
                    "mime_type": "image/png",
                    "response_id": "v1_turn_one",
                    "status": "completed",
                }
            ),
        )

    def handle_attempt_1_judge(argv: list[str], _timeout: int) -> StubProcResult:
        assert argv[:2] == ["gemini-api", "generate"]
        body = json.loads(argv[argv.index("--body") + 1])
        assert body["store"] is False
        assert body["generation_config"]["thinking_level"] == "high"
        judge_prompts_seen.append(argv[2])
        # Extract AC IDs from prompt so 3 of 4 pass (75% >= 70%) -> edit_turn
        ac_ids = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
        results = []
        for ac in ac_ids:
            is_text = ac["category"] == "text"
            results.append(
                {
                    "id": ac["id"],
                    "passed": not is_text,
                    "observed_evidence": "Typo in label" if is_text else "Matches requirement cleanly.",
                    "fix_instruction": "Fix label spelling to 'Gateway'." if is_text else "",
                }
            )
        verdict = {
            "overall_pass": False,
            "criteria_results": results,
            "remediation_mode": "edit_turn",
            "edit_delta_prompt": "Keep everything else the same. Fix label spelling to 'Gateway'.",
            "regenerated_prompt": "",
        }
        return StubProcResult(0, _wrap_generate_json(verdict, "judge_1"))

    def handle_attempt_2_edit(argv: list[str], _timeout: int) -> StubProcResult:
        assert argv[:2] == ["gemini-api", "image"]
        assert "--previous-interaction-id" in argv
        prev_idx = argv.index("--previous-interaction-id")
        assert argv[prev_idx + 1] == "v1_turn_one"
        assert "Keep everything else the same" in argv[2]
        # Simulate gemini-api rewriting --out extension if needed
        staged_out = Path(argv[argv.index("--out") + 1])
        staged_out.write_bytes(good_png_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged_out),
                    "size_bytes": len(good_png_bytes),
                    "mime_type": "image/png",
                    "response_id": "v1_turn_two",
                    "status": "completed",
                }
            ),
        )

    def handle_attempt_2_judge(argv: list[str], _timeout: int) -> StubProcResult:
        judge_prompts_seen.append(argv[2])
        ac_ids = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
        verdict = _all_passing_verdict_for({"acceptance_criteria": ac_ids})
        return StubProcResult(0, _wrap_generate_json(verdict, "judge_2"))

    runner = FakeGeminiRunner(
        [
            handle_attempt_1_gen,
            handle_attempt_1_judge,
            handle_attempt_2_edit,
            handle_attempt_2_judge,
        ]
    )

    rc = image_gen.main(
        [
            "--prompt",
            'Clean architecture diagram with box "Gateway" and service nodes',
            "--mode",
            "diagram",
            "--style",
            "clean dark vector",
            "--ar",
            "16:9",
            "--raw-prompt",
            "--max-attempts",
            "2",
            "--output",
            str(out_file),
        ],
        runner=runner,
    )
    assert rc == 0
    assert out_file.read_bytes() == good_png_bytes
    # Frozen spec invariant: exact same AC JSON judged on Attempt 1 and Attempt 2
    assert len(judge_prompts_seen) == 2
    assert judge_prompts_seen[0] == judge_prompts_seen[1]

    prov = json.loads(Path(f"{out_file}.provenance.json").read_text(encoding="utf-8"))
    assert prov["status"] == "VERIFIED"
    assert prov["attempts_used"] == 2
    assert prov["response_id"] == "v1_turn_two"


def test_t4_exhausted_retries_exit_one_write_rejected_and_never_touch_output(tmp_path: Path) -> None:
    out_file = tmp_path / "failed_banner.png"
    wrong_ar_bytes = (KNOWN_BAD_DIR / "wrong_ar_1x1_1024x1024.png").read_bytes()

    def always_wrong_ar(argv: list[str], _timeout: int) -> StubProcResult:
        # Mechanical failure on Attempt 1 -> Attempt 2 MUST regenerate (no --previous-interaction-id)
        assert "--previous-interaction-id" not in argv
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(wrong_ar_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "size_bytes": len(wrong_ar_bytes),
                    "mime_type": "image/png",
                    "response_id": "v1_bad_ar",
                    "status": "completed",
                }
            ),
        )

    runner = FakeGeminiRunner([always_wrong_ar, always_wrong_ar])
    rc = image_gen.main(
        [
            "--prompt",
            "Wide hero cloud skyline",
            "--ar",
            "16:9",
            "--raw-prompt",
            "--max-attempts",
            "2",
            "--output",
            str(out_file),
        ],
        runner=runner,
    )
    assert rc == 1
    assert not out_file.exists()
    rejected_path = tmp_path / "failed_banner.rejected.png"
    report_path = Path(f"{out_file}.report.json")
    assert rejected_path.read_bytes() == wrong_ar_bytes
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "REJECTED"
    assert report["attempts_used"] == 2
    assert any("aspect ratio" in err.lower() for err in report["last_mechanical"]["errors"])


def test_allow_unverified_override_writes_output_with_unverified_provenance(tmp_path: Path) -> None:
    out_file = tmp_path / "override_banner.png"
    wrong_ar_bytes = (KNOWN_BAD_DIR / "wrong_ar_1x1_1024x1024.png").read_bytes()

    def one_bad(argv: list[str], _timeout: int) -> StubProcResult:
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(wrong_ar_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "size_bytes": len(wrong_ar_bytes),
                    "mime_type": "image/png",
                    "response_id": "v1_override",
                    "status": "completed",
                }
            ),
        )

    # T4: Missing or blank --override-reason fails closed (exit 2) before calling gemini-api
    guard_runner = FakeGeminiRunner([one_bad])
    for extra in ([], ["--override-reason", "   "]):
        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_missing = image_gen.main(
                [
                    "--prompt",
                    "Wide hero cloud skyline",
                    "--ar",
                    "16:9",
                    "--raw-prompt",
                    "--max-attempts",
                    "1",
                    "--allow-unverified",
                    *extra,
                    "--output",
                    str(out_file),
                ],
                runner=guard_runner,
            )
        assert rc_missing == 2
        assert "--override-reason" in err_buf.getvalue()
        assert guard_runner.calls == []
        assert not out_file.exists()

    # Valid --override-reason exits 0 with loud WARNING on stderr, .provenance.json, and .report.json
    reason = "Manual waiver for 1:1 draft review"
    runner = FakeGeminiRunner([one_bad])
    warn_buf = io.StringIO()
    with contextlib.redirect_stderr(warn_buf):
        rc = image_gen.main(
            [
                "--prompt",
                "Wide hero cloud skyline",
                "--ar",
                "16:9",
                "--raw-prompt",
                "--max-attempts",
                "1",
                "--allow-unverified",
                "--override-reason",
                reason,
                "--output",
                str(out_file),
            ],
            runner=runner,
        )
    assert rc == 0
    assert "WARNING" in warn_buf.getvalue()
    assert reason in warn_buf.getvalue()
    assert out_file.read_bytes() == wrong_ar_bytes

    prov = json.loads(Path(f"{out_file}.provenance.json").read_text(encoding="utf-8"))
    assert prov["status"] == "UNVERIFIED_OVERRIDE"
    assert prov["override_reason"] == reason

    rep = json.loads(Path(f"{out_file}.report.json").read_text(encoding="utf-8"))
    assert rep["status"] == "UNVERIFIED_OVERRIDE"
    assert rep["override_reason"] == reason


# ---------------------------------------------------------------------------
# Sequential --manifest continuity & large-file files/ upload caching
# ---------------------------------------------------------------------------


def test_sequential_manifest_conditions_frame_k_plus_1_on_anchor_and_frame_k(tmp_path: Path) -> None:
    good_16x9 = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    manifest_in = tmp_path / "storyboard_in.json"
    manifest_out = tmp_path / "out" / "keyframes_manifest.json"
    manifest_in.write_text(
        json.dumps(
            {
                "mode": "timeline",
                "style": "ligne claire comic",
                "aspect_ratio": "16:9",
                "anchor_prompt": "Character sheet of astronomer Maya in observatory",
                "frames": [
                    {
                        "prompt": "Maya opens the dome shutters at dusk",
                        "caption": "Step 1",
                        "duration_s": 5,
                    },
                    {
                        "prompt": "Maya aligns the brass telescope toward Saturn",
                        "caption": "Step 2",
                        "duration_s": 6,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    image_calls_refs: list[list[str]] = []
    uploaded_paths: list[str] = []
    seq_counter = {"n": 0}

    def dynamic_handler(argv: list[str], _timeout: int) -> StubProcResult:
        if argv[:3] == ["gemini-api", "files", "upload"]:
            src = argv[3]
            uploaded_paths.append(Path(src).name)
            return StubProcResult(0, f"files/uploaded_{len(uploaded_paths)}\n")
        if argv[:2] == ["gemini-api", "image"]:
            seq_counter["n"] += 1
            refs = [argv[i + 1] for i, tok in enumerate(argv) if tok == "-i"]
            image_calls_refs.append(refs)
            staged = Path(argv[argv.index("--out") + 1])
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(good_16x9)
            return StubProcResult(
                0,
                json.dumps(
                    {
                        "kind": "image",
                        "path": str(staged),
                        "size_bytes": len(good_16x9),
                        "mime_type": "image/png",
                        "response_id": f"v1_seq_{seq_counter['n']}",
                        "status": "completed",
                    }
                ),
            )
        if argv[:2] == ["gemini-api", "generate"]:
            ac_ids = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
            return StubProcResult(0, _wrap_generate_json(_all_passing_verdict_for({"acceptance_criteria": ac_ids})))
        raise AssertionError(f"Unexpected command: {argv}")

    runner = FakeGeminiRunner([dynamic_handler] * 12)
    rc = image_gen.main(
        [
            "--manifest",
            str(manifest_in),
            "--manifest-out",
            str(manifest_out),
            "--raw-prompt",
            "--output",
            str(tmp_path / "out"),
        ],
        runner=runner,
    )
    assert rc == 0
    manifest_written = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert manifest_written["schema_version"] == 1
    assert manifest_written["mode"] == "timeline"
    assert manifest_written["style"] == "ligne claire comic"
    assert manifest_written["aspect_ratio"] == "16:9"
    assert len(manifest_written["frames"]) == 2
    assert [f["index"] for f in manifest_written["frames"]] == [1, 2]
    assert [f["duration_s"] for f in manifest_written["frames"]] == [5, 6]
    assert [f["response_id"] for f in manifest_written["frames"]] == ["v1_seq_2", "v1_seq_3"]

    # Anchor generated unreferenced; Frame 1 gets [anchor]; Frame 2 gets [anchor, frame_01]
    assert len(image_calls_refs) == 3
    assert image_calls_refs[0] == []
    assert len(image_calls_refs[1]) == 1
    assert len(image_calls_refs[2]) == 2
    assert image_calls_refs[2][0] == image_calls_refs[1][0]
    assert image_calls_refs[2][1] != image_calls_refs[2][0]


# ---------------------------------------------------------------------------
# --doctor auth shadowing & --help parity (S6) & real subprocess E2E (T5)
# ---------------------------------------------------------------------------


def test_doctor_warns_when_gemini_api_key_shadows_keyring() -> None:
    def whoami_and_ver(argv: list[str], _timeout: int) -> StubProcResult:
        if "--version" in argv:
            return StubProcResult(0, "gemini-api 0.4.2\n")
        if "whoami" in argv:
            return StubProcResult(
                0,
                json.dumps({"authenticated": True, "source": "keyring", "account": "dev"}),
            )
        raise AssertionError(f"Unexpected doctor argv: {argv}")

    runner_shadow = FakeGeminiRunner([whoami_and_ver, whoami_and_ver])
    report_shadow = image_gen.run_doctor(
        runner=runner_shadow,
        env={"PATH": os.environ.get("PATH", ""), "GEMINI_API_KEY": "shadow-test-value"},
        which_fn=lambda _name: "/usr/local/bin/gemini-api",
    )
    assert report_shadow["ready"] is True
    assert report_shadow["env_api_key_shadow_warning"] is True

    runner_clean = FakeGeminiRunner([whoami_and_ver, whoami_and_ver])
    report_clean = image_gen.run_doctor(
        runner=runner_clean,
        env={"PATH": os.environ.get("PATH", "")},
        which_fn=lambda _name: "/usr/local/bin/gemini-api",
    )
    assert report_clean["ready"] is True
    assert report_clean["env_api_key_shadow_warning"] is False

    report_missing = image_gen.run_doctor(
        runner=FakeGeminiRunner(),
        env={"PATH": ""},
        which_fn=lambda _name: None,
    )
    assert report_missing["ready"] is False


def test_t5_real_subprocess_cli_verify_only_and_dry_run_and_s6_help_parity() -> None:
    # S6: Every long flag documented in SKILL.md exists in `image_gen.py --help`
    help_proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_proc.returncode == 0
    help_text = help_proc.stdout
    for required_flag in (
        "--prompt",
        "--spec-file",
        "--mode",
        "--style",
        "--reference",
        "--references",
        "--ar",
        "--size",
        "--output",
        "--manifest",
        "--manifest-out",
        "--previous-interaction-id",
        "--model",
        "--verifier-model",
        "--max-attempts",
        "--raw-prompt",
        "--no-verify",
        "--allow-unverified",
        "--override-reason",
        "--dry-run",
        "--doctor",
        "--verify-only",
    ):
        assert required_flag in help_text, f"Missing flag {required_flag} in --help"

    skill_md_path = SKILL_DIR / "SKILL.md"
    if skill_md_path.is_file():
        import re

        skill_md = skill_md_path.read_text(encoding="utf-8")
        # Extract flags attached to image_gen.py examples in SKILL.md
        for line in skill_md.splitlines():
            if "image_gen.py" in line or line.strip().startswith("--"):
                for match in re.findall(r"(--[a-z][a-z0-9-]*)", line):
                    if match == "--with-media-tools":
                        continue
                    assert match in help_text, f"SKILL.md documents {match} not in --help"

    # Real subprocess dry-run outputs valid JSON plan
    dry_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--prompt",
            'Comic strip with "Hello World" speech bubble',
            "--mode",
            "comic-grid",
            "--ar",
            "1:1",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_proc.returncode == 0
    dry_payload = json.loads(dry_proc.stdout)
    assert dry_payload["spec"]["mode"] == "comic-grid"
    assert dry_payload["spec"]["image_size"] == "2K"
    assert dry_payload["model_chain"][0] == "gemini-3-pro-image"

    # Real subprocess --verify-only accepts known_good and rejects known_bad
    good_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--verify-only",
            str(KNOWN_GOOD_DIR / "valid_16x9_1344x768.png"),
            "--spec-file",
            str(KNOWN_GOOD_DIR / "sample_spec_16x9.json"),
            "--rubric-file",
            str(KNOWN_GOOD_DIR / "passing_rubric.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert good_proc.returncode == 0

    bad_proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--verify-only",
            str(KNOWN_GOOD_DIR / "valid_16x9_1344x768.png"),
            "--spec-file",
            str(KNOWN_GOOD_DIR / "sample_spec_16x9.json"),
            "--rubric-file",
            str(KNOWN_BAD_DIR / "contradictory_rubric.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_proc.returncode == 1

    # Real subprocess E2E with executable PATH-stubbed gemini-api script
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        bin_dir = tmp_dir / "bin"
        bin_dir.mkdir()
        stub_cli = bin_dir / "gemini-api"
        good_bytes_hex = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes().hex()
        stub_cli.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            "argv = sys.argv[1:]\n"
            "if argv[0] == 'image':\n"
            "    out = pathlib.Path(argv[argv.index('--out') + 1])\n"
            "    real_out = out.with_suffix('.png')\n"
            f"    real_out.write_bytes(bytes.fromhex('{good_bytes_hex}'))\n"
            "    print(json.dumps({'kind':'image','path':str(real_out),'size_bytes':205,"
            "'mime_type':'image/png','response_id':'v1_e2e','status':'completed'}))\n"
            "elif argv[0] == 'generate':\n"
            "    prompt = argv[1]\n"
            "    if 'ACCEPTANCE_CRITERIA_JSON:' in prompt:\n"
            "        acs = json.loads(prompt.split('ACCEPTANCE_CRITERIA_JSON:\\n', 1)[1])\n"
            "        verdict = {'overall_pass': True, 'criteria_results': ["
            "{'id': a['id'], 'passed': True, 'observed_evidence': 'Clear match', 'fix_instruction': ''} for a in acs],"
            "'remediation_mode': 'edit_turn', 'edit_delta_prompt': '', 'regenerated_prompt': ''}\n"
            "        print(json.dumps({'id':'j1','status':'completed','steps':[{'type':'model_output',"
            "'content':[{'type':'text','text':json.dumps(verdict)}]}]}))\n"
            "    else:\n"
            "        exp = {'expanded_prompt': prompt}\n"
            "        print(json.dumps({'id':'e1','status':'completed','steps':[{'type':'model_output',"
            "'content':[{'type':'text','text':json.dumps(exp)}]}]}))\n",
            encoding="utf-8",
        )
        stub_cli.chmod(stub_cli.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        target_out = tmp_dir / "final_hero.jpg"  # Note .jpg requested while CLI rewrites to .png!
        env = dict(os.environ)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
        e2e_proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--prompt",
                "Wide isometric cloud diagram",
                "--ar",
                "16:9",
                "--raw-prompt",
                "--output",
                str(target_out),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert e2e_proc.returncode == 0
        real_out_png = tmp_dir / "final_hero.png"
        assert not target_out.exists()
        assert real_out_png.is_file()
        assert Path(f"{real_out_png}.provenance.json").is_file()
        prov_e2e = json.loads(Path(f"{real_out_png}.provenance.json").read_text(encoding="utf-8"))
        assert prov_e2e["output"] == str(real_out_png)
        assert prov_e2e["requested_output"] == str(target_out)
        assert prov_e2e["mechanical"]["mime_type"] == "image/png"
        stdout_e2e = json.loads(e2e_proc.stdout.strip())
        assert stdout_e2e["output"] == str(real_out_png)


def test_expand_prompt_via_cli_preserves_quotes_and_falls_back_when_dropped() -> None:
    spec = image_gen.compile_spec(
        prompt='Diagram with node "Edge Proxy" connected to "Core Vault"',
        mode="diagram",
        style="dark vector",
        aspect_ratio="16:9",
        image_size="1K",
        references=[],
    )
    good_expanded = (
        'Crisp orthographic dark-vector diagram showing "Edge Proxy" wired by glowing '
        'cyan bus to "Core Vault" on a slate grid.'
    )
    runner_good = FakeGeminiRunner(
        [StubProcResult(0, _wrap_generate_json({"expanded_prompt": good_expanded}))]
    )
    enriched = image_gen.expand_prompt_via_cli(spec, image_gen.VERIFIER_MODEL_CHAIN, runner_good)
    assert enriched == good_expanded

    dropped_expanded = 'Crisp orthographic dark-vector diagram showing "Edge Proxy" wired to vault.'
    runner_drop = FakeGeminiRunner(
        [StubProcResult(0, _wrap_generate_json({"expanded_prompt": dropped_expanded}))]
    )
    fallback = image_gen.expand_prompt_via_cli(spec, image_gen.VERIFIER_MODEL_CHAIN, runner_drop)
    assert fallback == spec["compiled_prompt"]


def test_asset_cache_uploads_files_over_12mb_once_and_passes_files_uris(tmp_path: Path) -> None:
    big_ref = tmp_path / "huge_anchor.png"
    valid_prefix = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    with big_ref.open("wb") as handle:
        handle.write(valid_prefix)
        handle.seek(image_gen.UPLOAD_THRESHOLD_BYTES + 128)
        handle.write(b"\x00")

    runner = FakeGeminiRunner([StubProcResult(0, '{"uri": "files/big_anchor_99"}\n')])
    cache = image_gen.AssetCache(runner)

    # Existing files/ URI never triggers upload
    assert cache.resolve("files/already_uploaded") == "files/already_uploaded"
    assert runner.calls == []

    # >12MB local file uploads once and is cached on second lookup
    uri_first = cache.resolve(str(big_ref))
    uri_second = cache.resolve(str(big_ref))
    assert uri_first == "files/big_anchor_99"
    assert uri_second == "files/big_anchor_99"
    assert len(runner.calls) == 1
    assert runner.calls[0][:3] == ["gemini-api", "files", "upload"]


def test_model_and_verifier_429_503_quota_failover_chains(tmp_path: Path, capsys: Any) -> None:
    out_file = tmp_path / "failover.png"
    good_png = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()

    def gen_429_primary(_argv: list[str], _timeout: int) -> StubProcResult:
        return StubProcResult(1, "", "429 RESOURCE_EXHAUSTED on gemini-nano-banana-2.1")

    def gen_ok_backup(argv: list[str], _timeout: int) -> StubProcResult:
        assert argv[argv.index("-m") + 1] == "gemini-3-pro-image"
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(good_png)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "size_bytes": len(good_png),
                    "mime_type": "image/png",
                    "response_id": "v1_backup_ok",
                    "status": "completed",
                }
            ),
        )

    def judge_503(_argv: list[str], _timeout: int) -> StubProcResult:
        return StubProcResult(1, "", "503 Service Unavailable")

    def judge_flash_emergency(argv: list[str], _timeout: int) -> StubProcResult:
        assert argv[argv.index("-m") + 1] == "gemini-3.8-flash"
        acs = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
        return StubProcResult(0, _wrap_generate_json(_all_passing_verdict_for({"acceptance_criteria": acs})))

    runner = FakeGeminiRunner([gen_429_primary, gen_ok_backup, judge_503, judge_503, judge_flash_emergency])
    rc = image_gen.main(
        [
            "--prompt",
            "Minimalist mountain horizon at dawn",
            "--mode",
            "single",
            "--ar",
            "16:9",
            "--raw-prompt",
            "--max-attempts",
            "1",
            "--output",
            str(out_file),
        ],
        runner=runner,
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "gemini-3.8-flash" in captured.err
    prov = json.loads(Path(f"{out_file}.provenance.json").read_text(encoding="utf-8"))
    assert prov["model"] == "gemini-3-pro-image"
    assert prov["verifier_model"] == "gemini-3.8-flash"


def test_no_verify_still_enforces_stage3_mechanical_gate(tmp_path: Path) -> None:
    good_out = tmp_path / "mech_good.png"
    bad_out = tmp_path / "mech_bad.png"
    good_bytes = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    bad_bytes = (KNOWN_BAD_DIR / "wrong_ar_1x1_1024x1024.png").read_bytes()

    def write_bytes_handler(payload: bytes) -> Any:
        def _inner(argv: list[str], _timeout: int) -> StubProcResult:
            staged = Path(argv[argv.index("--out") + 1])
            staged.write_bytes(payload)
            return StubProcResult(
                0,
                json.dumps(
                    {
                        "kind": "image",
                        "path": str(staged),
                        "size_bytes": len(payload),
                        "mime_type": "image/png",
                        "response_id": "v1_mech",
                        "status": "completed",
                    }
                ),
            )

        return _inner

    rc_good = image_gen.main(
        ["--prompt", "Hero graphic", "--ar", "16:9", "--raw-prompt", "--no-verify", "-o", str(good_out)],
        runner=FakeGeminiRunner([write_bytes_handler(good_bytes)]),
    )
    assert rc_good == 0
    prov = json.loads(Path(f"{good_out}.provenance.json").read_text(encoding="utf-8"))
    assert prov["status"] == "MECHANICALLY_VERIFIED_ONLY"
    assert any("--no-verify" in item for item in prov["unchecked_surfaces"])

    rc_bad = image_gen.main(
        [
            "--prompt",
            "Hero graphic",
            "--ar",
            "16:9",
            "--raw-prompt",
            "--no-verify",
            "--max-attempts",
            "1",
            "-o",
            str(bad_out),
        ],
        runner=FakeGeminiRunner([write_bytes_handler(bad_bytes)]),
    )
    assert rc_bad == 1
    assert not bad_out.exists()


def test_webp_vp8l_lossless_header_and_role_tagged_comma_references() -> None:
    import struct

    w, h = 1280, 720
    bits = ((w - 1) & 0x3FFF) | (((h - 1) & 0x3FFF) << 14)
    vp8l_payload = b"\x2f" + struct.pack("<I", bits) + b"\x00"
    chunk = b"VP8L" + struct.pack("<I", len(vp8l_payload)) + vp8l_payload
    riff = b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk
    info = image_gen.inspect_image_header(riff)
    assert info["mime_type"] == "image/webp"
    assert (info["width"], info["height"]) == (1280, 720)

    refs = image_gen.parse_reference_arg(
        ["char:hero.png,style:mood.png", "prop:key.png", r"C:\assets\win_ref.png"]
    )
    assert refs == [
        {"role": "char", "path": "hero.png"},
        {"role": "style", "path": "mood.png"},
        {"role": "prop", "path": "key.png"},
        {"role": "ref", "path": r"C:\assets\win_ref.png"},
    ]

    # Verify target_mime_for_output, role binding sentence in compiled_prompt, and compute_spec_digest
    assert image_gen.target_mime_for_output(Path("diagram.png")) == "image/png"
    assert image_gen.target_mime_for_output(Path("photo.jpeg")) == "image/jpeg"
    assert image_gen.target_mime_for_output(Path("card.webp")) == "image/webp"

    spec_with_roles = image_gen.compile_spec(
        prompt="Hero standing in workshop",
        mode="single",
        style="cel shaded",
        aspect_ratio="16:9",
        image_size="1K",
        references=refs[:3],
    )
    spec_without_roles = image_gen.compile_spec(
        prompt="Hero standing in workshop",
        mode="single",
        style="cel shaded",
        aspect_ratio="16:9",
        image_size="1K",
        references=[],
    )
    assert "locks character identity" in spec_with_roles["compiled_prompt"]
    assert "locks colour palette" in spec_with_roles["compiled_prompt"]
    assert "locks object/prop geometry" in spec_with_roles["compiled_prompt"]
    assert "Reference grounding:" not in spec_without_roles["compiled_prompt"]

    digest_a = image_gen.compute_spec_digest(spec_with_roles)
    digest_b = image_gen.compute_spec_digest(spec_without_roles)
    assert isinstance(digest_a, str) and len(digest_a) == 64
    assert digest_a != digest_b


def test_p1_s8_default_runner_redacts_secrets_and_handles_missing_and_timeout(tmp_path: Path) -> None:
    leaked_google = "AIza" + "SyTestRedaction0123456789abcdefghijk"
    leaked_ant = "sk-ant-" + "api03-TestRedaction0123456789abc"
    leaked_env_val = "dummySecretValue_987654321"
    leaked_bare_key = "bareCredToken_1234567890abcdef"
    leaked_b64_key = "Ab3+Xyz/" + "1234567890" + "+/TAIL=="
    leaked_json_key = "jsonBareToken_9876543210fedcba"
    # 1. Real subprocess via default_runner emitting secrets across URL query, JSON env, api_key, bare/base64 key=, stderr
    # REV-003: Redaction preserves valid JSON structure so json.loads(proc.stdout) succeeds.
    proc = image_gen.default_runner(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                f"print('{{\"GEMINI_API_KEY\": \"{leaked_env_val}\", \"key\": \"{leaked_json_key}\", \"status\": \"ok\"}}');"
                f"sys.stderr.write('https://example.test?key={leaked_google}&x=1 api_key: secret_abc "
                f"key={leaked_bare_key} key={leaked_b64_key} key=char {leaked_ant}\\n')"
            ),
        ],
        timeout=15,
    )
    assert proc.returncode == 0
    parsed_stdout = json.loads(proc.stdout)
    assert parsed_stdout["status"] == "ok"
    assert leaked_env_val not in parsed_stdout["GEMINI_API_KEY"]
    assert leaked_json_key not in parsed_stdout["key"]
    assert leaked_google not in proc.stderr
    assert leaked_ant not in proc.stderr
    assert leaked_env_val not in proc.stdout
    assert leaked_json_key not in proc.stdout
    assert leaked_bare_key not in proc.stderr
    assert leaked_b64_key not in proc.stderr
    assert "TAIL==" not in proc.stderr
    assert "key=char" in proc.stderr
    assert "secret_abc" not in proc.stderr
    assert "[REDACTED]" in proc.stderr or "[REDACTED:" in proc.stderr

    # NIT-010: JSON literals (null/true/false/numbers/empty string) stay valid JSON & unredacted
    json_edge_payload = json.dumps(
        {
            "api_key": None,
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": False,
            "key": None,
            "api_key_num": 42,
            "nested": {"api_key": 123, "real_secret": {"api_key": "secret_xyz_99"}},
        }
    )
    redacted_edge = image_gen.redact_secrets(json_edge_payload)
    parsed_edge = json.loads(redacted_edge)
    assert parsed_edge["api_key"] is None
    assert parsed_edge["GEMINI_API_KEY"] == ""
    assert parsed_edge["GOOGLE_API_KEY"] is False
    assert parsed_edge["key"] is None
    assert parsed_edge["nested"]["api_key"] == 123
    assert "secret_xyz_99" not in parsed_edge["nested"]["real_secret"]["api_key"]
    assert "[REDACTED:API key field]" == parsed_edge["nested"]["real_secret"]["api_key"]

    # 2. P2 #10: Missing binary returns rc 127 cleanly instead of raising FileNotFoundError
    missing_proc = image_gen.default_runner(["/nonexistent/binary/definitely-missing-xyz"], timeout=5)
    assert missing_proc.returncode == 127
    assert "Command not found" in missing_proc.stderr

    # 3. P2 #10: Timed-out command returns rc 124 and redacts output instead of raising TimeoutExpired
    timeout_proc = image_gen.default_runner(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout=1,
    )
    assert timeout_proc.returncode == 124
    assert "timed out" in timeout_proc.stderr.lower()

    # 4. P1 #1: Error diagnostic report & run_doctor also redact secrets from custom runners
    fake_out = tmp_path / "fail.png"

    def leaking_fail(_argv: list[str], _timeout: int) -> StubProcResult:
        return StubProcResult(1, "", f"429 quota for key={leaked_google} api_key={leaked_env_val}")

    rc_fail = image_gen.main(
        ["--prompt", "Hero graphic", "--raw-prompt", "--max-attempts", "1", "-o", str(fake_out)],
        runner=FakeGeminiRunner([leaking_fail, leaking_fail, leaking_fail]),
    )
    assert rc_fail == 1
    rep_text = Path(f"{fake_out}.report.json").read_text(encoding="utf-8")
    assert leaked_google not in rep_text
    assert leaked_env_val not in rep_text

    doc = image_gen.run_doctor(
        runner=FakeGeminiRunner(
            [
                StubProcResult(0, "0.5.0\n"),
                StubProcResult(0, f"GEMINI_API_KEY={leaked_env_val}"),
            ]
        ),
        env={},
        which_fn=lambda _n: "/usr/bin/gemini-api",
    )
    assert leaked_env_val not in json.dumps(doc)


def test_p1_rejects_non_image_or_escaping_references_anchors_and_spec_refs(tmp_path: Path) -> None:
    non_img = KNOWN_BAD_DIR / "non_image_anchor.txt"
    called = {"count": 0}

    def should_not_run(_argv: list[str], _timeout: int) -> StubProcResult:
        called["count"] += 1
        return StubProcResult(0, "{}")

    # 1. Manifest non-image anchor_image exits 2 before calling gemini-api
    rc_bad_anchor = image_gen.main(
        [
            "--manifest",
            str(KNOWN_BAD_DIR / "manifest_non_image_anchor.json"),
            "--raw-prompt",
            "--output",
            str(tmp_path / "seq1"),
        ],
        runner=should_not_run,
    )
    assert rc_bad_anchor == 2

    # 2. Manifest path-traversal anchor_image exits 2 before calling gemini-api
    rc_traversal = image_gen.main(
        [
            "--manifest",
            str(KNOWN_BAD_DIR / "manifest_traversal.json"),
            "--raw-prompt",
            "--output",
            str(tmp_path / "seq2"),
        ],
        runner=should_not_run,
    )
    assert rc_traversal == 2

    # 3. CLI -r non-image path exits 2 before calling gemini-api
    rc_cli_ref = image_gen.main(
        [
            "--prompt",
            "Portrait",
            "-r",
            str(non_img),
            "--raw-prompt",
            "--output",
            str(tmp_path / "portrait.png"),
        ],
        runner=should_not_run,
    )
    assert rc_cli_ref == 2

    # 4. --spec-file referencing a non-image file exits 2 before calling gemini-api
    bad_spec = dict(json.loads((KNOWN_GOOD_DIR / "sample_spec_16x9.json").read_text(encoding="utf-8")))
    bad_spec["explicit_constraints"] = dict(bad_spec["explicit_constraints"])
    bad_spec["explicit_constraints"]["references"] = [{"role": "style", "path": str(non_img)}]
    bad_spec_path = tmp_path / "bad_ref_spec.json"
    bad_spec_path.write_text(json.dumps(bad_spec), encoding="utf-8")
    rc_spec_ref = image_gen.main(
        [
            "--spec-file",
            str(bad_spec_path),
            "--raw-prompt",
            "--output",
            str(tmp_path / "from_spec.png"),
        ],
        runner=should_not_run,
    )
    assert rc_spec_ref == 2
    assert called["count"] == 0


def test_p1_verify_only_rejects_mismatched_extension_binary_fixture() -> None:
    rc = image_gen.main(
        [
            "--verify-only",
            str(KNOWN_BAD_DIR / "mismatched_ext_png_as_jpg.jpg"),
            "--ar",
            "16:9",
            "--size",
            "1K",
        ]
    )
    assert rc == 1


def test_p1_rejects_zero_mandatory_ac_spec_and_bad_verifier_and_p2_lite_fence(tmp_path: Path) -> None:
    # 1. P1 #6: validate_rubric_verdict fails closed when all ACs are mandatory=False
    zero_spec = json.loads((KNOWN_BAD_DIR / "zero_mandatory_spec.json").read_text(encoding="utf-8"))
    verdict_eval = image_gen.validate_rubric_verdict(
        {
            "overall_pass": True,
            "criteria_results": [
                {"id": "AC-1", "passed": True, "observed_evidence": "Looks fine", "fix_instruction": ""}
            ],
        },
        zero_spec,
    )
    assert verdict_eval["passed"] is False
    assert verdict_eval["structural_error"] is True

    # CLI --spec-file with zero mandatory ACs exits 2
    rc_zero = image_gen.main(
        [
            "--spec-file",
            str(KNOWN_BAD_DIR / "zero_mandatory_spec.json"),
            "--dry-run",
            "-o",
            str(tmp_path / "out.png"),
        ]
    )
    assert rc_zero == 2

    # 2. P1 #8: verifier allowlist blocks lite image model and video model
    for bad_ver in ("gemini-3.1-flash-lite-image", "gemini-omni-1.2-flash", "gemini-nano-banana-2.1"):
        rc_ver = image_gen.main(
            [
                "--prompt",
                "Hero icon",
                "--verifier-model",
                bad_ver,
                "--dry-run",
            ]
        )
        assert rc_ver == 2

    # 3. P2 #12: explicit --model gemini-3.1-flash-lite-image blocked with refs / quotes / comic-grid
    for extra_args in (
        ["--prompt", "Hero", "-r", "ref.png"],
        ["--prompt", 'Logo reading "ACME"'],
        ["--prompt", "2x2 strip", "--mode", "comic-grid"],
    ):
        rc_lite = image_gen.main(
            [*extra_args, "--model", "gemini-3.1-flash-lite-image", "--dry-run"]
        )
        assert rc_lite == 2


def test_p2_remediation_style_and_structural_error_and_edit_turn_reset(tmp_path: Path) -> None:
    # 1. P2 #13: style failure & structural error (contradiction at 75% pass) force regenerate
    spec = json.loads((KNOWN_GOOD_DIR / "sample_spec_16x9.json").read_text(encoding="utf-8"))
    style_fail = json.loads((KNOWN_BAD_DIR / "rubric_style_fail.json").read_text(encoding="utf-8"))
    style_eval = image_gen.validate_rubric_verdict(style_fail, spec)
    assert style_eval["passed"] is False
    assert style_eval["pass_ratio"] == 0.75
    assert style_eval["core_style_failed"] is True
    assert (
        image_gen.select_remediation_mode(
            mechanical_passed=True, rubric_validation=style_eval, response_id="v1_r1"
        )
        == "regenerate"
    )

    contradictory = json.loads((KNOWN_BAD_DIR / "contradictory_rubric.json").read_text(encoding="utf-8"))
    contra_eval = image_gen.validate_rubric_verdict(contradictory, spec)
    assert contra_eval["structural_error"] is True
    assert (
        image_gen.select_remediation_mode(
            mechanical_passed=True, rubric_validation=contra_eval, response_id="v1_r1"
        )
        == "regenerate"
    )

    # 2. P2 #9: After edit_turn + failed generation attempt, prompt resets to base_prompt (not delta!)
    good_bytes = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    seen_gen_prompts: list[tuple[str, bool]] = []

    def gen_ok_1(argv: list[str], _timeout: int) -> StubProcResult:
        seen_gen_prompts.append((argv[2], "--previous-interaction-id" in argv))
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(good_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "mime_type": "image/png",
                    "response_id": "v1_resp_1",
                }
            ),
        )

    def judge_text_fail(argv: list[str], _timeout: int) -> StubProcResult:
        acs = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
        results = [
            {
                "id": ac["id"],
                "passed": ac["category"] != "text",
                "observed_evidence": "Checked.",
                "fix_instruction": "Fix quoted text." if ac["category"] == "text" else "",
            }
            for ac in acs
        ]
        return StubProcResult(
            0,
            json.dumps(
                {
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        {
                                            "overall_pass": False,
                                            "criteria_results": results,
                                            "remediation_mode": "edit_turn",
                                            "edit_delta_prompt": "Keep everything else the same. Fix ONLY label typo.",
                                            "regenerated_prompt": "",
                                        }
                                    ),
                                }
                            ],
                        }
                    ]
                }
            ),
        )

    def gen_fail_all_models(argv: list[str], _timeout: int) -> StubProcResult:
        seen_gen_prompts.append((argv[2], "--previous-interaction-id" in argv))
        return StubProcResult(1, "", "503 upstream failed")

    def gen_ok_3(argv: list[str], _timeout: int) -> StubProcResult:
        seen_gen_prompts.append((argv[2], "--previous-interaction-id" in argv))
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(good_bytes)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "mime_type": "image/png",
                    "response_id": "v1_resp_3",
                }
            ),
        )

    def judge_all_pass(argv: list[str], _timeout: int) -> StubProcResult:
        acs = json.loads(argv[2].split("ACCEPTANCE_CRITERIA_JSON:\n", 1)[1])
        return StubProcResult(
            0,
            json.dumps(
                {
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        {
                                            "overall_pass": True,
                                            "criteria_results": [
                                                {
                                                    "id": a["id"],
                                                    "passed": True,
                                                    "observed_evidence": "All clear",
                                                    "fix_instruction": "",
                                                }
                                                for a in acs
                                            ],
                                            "remediation_mode": "edit_turn",
                                            "edit_delta_prompt": "",
                                            "regenerated_prompt": "",
                                        }
                                    ),
                                }
                            ],
                        }
                    ]
                }
            ),
        )

    out_png = tmp_path / "reset_test.png"
    runner = FakeGeminiRunner(
        [
            gen_ok_1,
            judge_text_fail,
            gen_fail_all_models,
            gen_fail_all_models,
            gen_ok_3,
            judge_all_pass,
        ]
    )
    rc = image_gen.main(
        [
            "--prompt",
            'Cloud mesh diagram reading "Gateway"',
            "--mode",
            "diagram",
            "--style",
            "dark vector",
            "--ar",
            "16:9",
            "--raw-prompt",
            "--max-attempts",
            "3",
            "-o",
            str(out_png),
        ],
        runner=runner,
    )
    assert rc == 0
    # Attempt 2 had delta + previous_interaction_id; Attempt 3 MUST reset to full base_prompt!
    assert seen_gen_prompts[1][1] is True
    assert seen_gen_prompts[1][0].startswith("Keep everything else the same.")
    assert seen_gen_prompts[3][1] is False
    assert "Cloud mesh diagram reading" in seen_gen_prompts[3][0]
    assert not seen_gen_prompts[3][0].startswith("Keep everything else the same.")


def test_p2_untrusted_path_escape_malformed_inputs_and_stale_provenance_cleanup(
    tmp_path: Path,
) -> None:
    # 1. P2 #11: Untrusted JSON `.path` outside staged dir is refused and outside file untouched
    outside_secret = tmp_path / "outside_untouched.png"
    outside_secret.write_bytes((KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes())

    def escaping_gen(argv: list[str], _timeout: int) -> StubProcResult:
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(outside_secret),
                    "mime_type": "image/png",
                    "response_id": "v1_evil",
                }
            ),
        )

    out_dir = tmp_path / "sub"
    out_dir.mkdir()
    target = out_dir / "hero.png"
    # Pre-create target AND stale provenance (P2 #15)
    target.write_bytes(b"stale image")
    stale_prov = Path(f"{target}.provenance.json")
    stale_prov.write_text('{"status": "STALE_OLD"}\n', encoding="utf-8")

    rc = image_gen.main(
        ["--prompt", "Hero graphic", "--raw-prompt", "--max-attempts", "1", "-o", str(target)],
        runner=FakeGeminiRunner([escaping_gen, escaping_gen, escaping_gen]),
    )
    assert rc == 1
    assert outside_secret.is_file()
    assert not target.exists()
    assert not stale_prov.exists()

    # 2. P2 #14: Malformed --spec-file, --manifest, and --rubric-file cleanly exit 2 (no traceback)
    assert image_gen.main(["--spec-file", str(KNOWN_BAD_DIR / "malformed_spec.json"), "--dry-run"]) == 2
    assert image_gen.main(["--manifest", str(KNOWN_BAD_DIR / "malformed_manifest.json"), "--dry-run"]) == 2
    assert (
        image_gen.main(
            [
                "--verify-only",
                str(KNOWN_GOOD_DIR / "valid_16x9_1344x768.png"),
                "--spec-file",
                str(KNOWN_GOOD_DIR / "sample_spec_16x9.json"),
                "--rubric-file",
                str(KNOWN_BAD_DIR / "invalid_rubric.json"),
            ]
        )
        == 2
    )


def test_r1_to_r5_rewrite_cleanup_manifest_containment_files_uri_and_spec_validation(
    tmp_path: Path,
) -> None:
    import contextlib
    import io

    good_png = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()

    # R5: manifest_traversal.json targets an existing file outside known_bad/ and triggers escapes check
    traversal_manifest = json.loads((KNOWN_BAD_DIR / "manifest_traversal.json").read_text(encoding="utf-8"))
    outside_target = (KNOWN_BAD_DIR / traversal_manifest["anchor_image"]).resolve()
    assert outside_target.is_file()
    err_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf):
        rc_trav = image_gen.main(
            ["--manifest", str(KNOWN_BAD_DIR / "manifest_traversal.json"), "--dry-run"]
        )
    assert rc_trav == 2
    assert "escapes" in err_buf.getvalue().lower()

    # R1: _finalize_verified_image unlinks stale requested-suffix file + provenance when rewriting suffix
    req_jpg = tmp_path / "start_frame.jpg"
    req_jpg.write_bytes(b"stale old jpg")
    req_jpg_prov = Path(f"{req_jpg}.provenance.json")
    req_jpg_prov.write_text('{"status": "STALE"}\n', encoding="utf-8")

    def png_writer(argv: list[str], _timeout: int) -> StubProcResult:
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(good_png)
        return StubProcResult(
            0,
            json.dumps(
                {
                    "kind": "image",
                    "path": str(staged),
                    "mime_type": "image/png",
                    "response_id": "v1_r1",
                }
            ),
        )

    rc_r1 = image_gen.main(
        ["--prompt", "Keyframe", "--ar", "16:9", "--raw-prompt", "--no-verify", "-o", str(req_jpg)],
        runner=FakeGeminiRunner([png_writer]),
    )
    assert rc_r1 == 0
    assert not req_jpg.exists()
    assert not req_jpg_prov.exists()
    assert (tmp_path / "start_frame.png").is_file()

    # R2: parent --manifest-out + external -r anchor stages anchor inside frames_dir (no '../' and no duplicate -i)
    ext_dir = tmp_path / "external_refs"
    ext_dir.mkdir()
    ext_hero = ext_dir / "hero_ext.png"
    ext_hero.write_bytes(good_png)
    parent_out = tmp_path / "bundle"
    parent_out.mkdir()
    manifest_in = tmp_path / "seq_in.json"
    manifest_in.write_text(
        json.dumps(
            {
                "mode": "timeline",
                "aspect_ratio": "16:9",
                "frames": [{"prompt": "Hero steps onto deck", "caption": "Step 1", "duration_s": 5}],
            }
        ),
        encoding="utf-8",
    )
    bad_manifest_out = parent_out / "nested" / "keyframes_manifest.json"
    assert (
        image_gen.main(
            [
                "--manifest",
                str(manifest_in),
                "--manifest-out",
                str(bad_manifest_out),
                "--raw-prompt",
                "--no-verify",
                "--output",
                str(parent_out / "seq_out"),
            ],
            runner=FakeGeminiRunner(),
        )
        == 2
    )

    good_manifest_out = parent_out / "keyframes_manifest.json"
    seen_refs: list[list[str]] = []

    def seq_png_writer(argv: list[str], _timeout: int) -> StubProcResult:
        if len(argv) >= 3 and argv[:3] == ["gemini-api", "files", "upload"]:
            return StubProcResult(0, json.dumps({"uri": "files/anchor_uploaded_1"}))
        seen_refs.append([argv[i + 1] for i, tok in enumerate(argv) if tok == "-i"])
        staged = Path(argv[argv.index("--out") + 1])
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(good_png)
        return StubProcResult(
            0,
            json.dumps(
                {"kind": "image", "path": str(staged), "mime_type": "image/png", "response_id": "v1_seq"}
            ),
        )

    rc_parent = image_gen.main(
        [
            "--manifest",
            str(manifest_in),
            "--manifest-out",
            str(good_manifest_out),
            "-r",
            str(ext_hero),
            "--raw-prompt",
            "--no-verify",
            "--output",
            str(parent_out / "seq_out"),
        ],
        runner=FakeGeminiRunner([seq_png_writer, seq_png_writer]),
    )
    assert rc_parent == 0
    written_m = json.loads(good_manifest_out.read_text(encoding="utf-8"))
    assert ".." not in written_m["anchor_image"]
    assert ".." not in written_m["frames"][0]["path"]
    assert (parent_out / written_m["anchor_image"]).is_file()
    assert len(seen_refs[0]) == 1

    # R3: files/<id> anchor passes manifest validation and forwards URI without file lookup
    files_manifest = tmp_path / "files_anchor.json"
    files_manifest.write_text(
        json.dumps(
            {
                "mode": "timeline",
                "aspect_ratio": "16:9",
                "anchor_image": "files/anchor_uri_42",
                "frames": [{"prompt": "Hero opens hatch", "duration_s": 5}],
            }
        ),
        encoding="utf-8",
    )
    files_seen_refs: list[list[str]] = []

    def files_uri_writer(argv: list[str], _timeout: int) -> StubProcResult:
        files_seen_refs.append([argv[i + 1] for i, tok in enumerate(argv) if tok == "-i"])
        return seq_png_writer(argv, _timeout)

    rc_files = image_gen.main(
        [
            "--manifest",
            str(files_manifest),
            "--raw-prompt",
            "--no-verify",
            "--output",
            str(tmp_path / "files_run"),
        ],
        runner=FakeGeminiRunner([files_uri_writer]),
    )
    assert rc_files == 0
    assert files_seen_refs[0] == ["files/anchor_uri_42"]
    emitted_files_m = json.loads((tmp_path / "files_run" / "keyframes_manifest.json").read_text(encoding="utf-8"))
    assert emitted_files_m["anchor_image"] == "files/anchor_uri_42"

    # R4: --spec-file missing AC category or invalid ref role exits 2 cleanly
    base_spec = json.loads((KNOWN_GOOD_DIR / "sample_spec_16x9.json").read_text(encoding="utf-8"))
    bad_cat_spec = json.loads(json.dumps(base_spec))
    del bad_cat_spec["acceptance_criteria"][0]["category"]
    bad_cat_path = tmp_path / "missing_cat_spec.json"
    bad_cat_path.write_text(json.dumps(bad_cat_spec), encoding="utf-8")
    assert image_gen.main(["--spec-file", str(bad_cat_path), "--dry-run"]) == 2

    bad_role_spec = json.loads(json.dumps(base_spec))
    bad_role_spec["explicit_constraints"]["references"] = [{"role": "", "path": "x.png"}]
    bad_role_path = tmp_path / "bad_role_spec.json"
    bad_role_path.write_text(json.dumps(bad_role_spec), encoding="utf-8")
    assert image_gen.main(["--spec-file", str(bad_role_path), "--dry-run"]) == 2

    # >12MB upload RuntimeError exits 1 cleanly instead of raising unhandled traceback
    big_img = tmp_path / "oversize_ref.png"
    with big_img.open("wb") as fh:
        fh.write(good_png)
        fh.seek(image_gen.UPLOAD_THRESHOLD_BYTES + 256)
        fh.write(b"\x00")
    assert (
        image_gen.main(
            [
                "--prompt",
                "Hero",
                "-r",
                str(big_img),
                "--raw-prompt",
                "-o",
                str(tmp_path / "fail_upload.png"),
            ],
            runner=FakeGeminiRunner([StubProcResult(1, "", "500 upload failed")]),
        )
        == 1
    )


def test_round2_positional_prompt_hyphen_escape_glob_and_stale_report_cleanup(tmp_path: Path) -> None:
    # SEC-001: Positional prompt starting with '-' cannot be parsed as a CLI flag
    hyphen_cmd = image_gen.build_image_cli_command(
        prompt="-m gemini-1.5-pro draw a skyline",
        model=image_gen.PRIMARY_IMAGE_MODEL,
        aspect_ratio="16:9",
        image_size="1K",
        out_path=tmp_path / "out.png",
        references=[],
        previous_interaction_id=None,
        mode="single",
        has_quoted_text=False,
        target_mime="image/png",
    )
    assert not hyphen_cmd[2].startswith("-")
    assert "-m gemini-1.5-pro draw a skyline" in hyphen_cmd[2]

    # Leading space + '-' also neutralized
    assert not image_gen.normalize_cli_positional_prompt("  --help").startswith("-")
    # Normal prompt untouched
    assert image_gen.normalize_cli_positional_prompt("Clean hero") == "Clean hero"

    # Main --dry-run with --prompt="- bullet" emits safe planned_command
    dry_buf = io.StringIO()
    with contextlib.redirect_stdout(dry_buf):
        rc_dry = image_gen.main(["--prompt=- bullet diagram", "--raw-prompt", "--dry-run"])
    assert rc_dry == 0
    dry_payload = json.loads(dry_buf.getvalue())
    assert not dry_payload["planned_command"][2].startswith("-")

    # NIT-001 & NIT-006: bracket filename 'hero[1].png' without 'path' field + stale .report.json cleanup
    good_png = (KNOWN_GOOD_DIR / "valid_16x9_1344x768.png").read_bytes()
    bracket_out = tmp_path / "hero[1].png"
    stale_report = Path(f"{bracket_out}.report.json")
    stale_report.write_text(json.dumps({"status": "REJECTED"}), encoding="utf-8")

    def gen_missing_path_field(argv: list[str], _timeout: int) -> StubProcResult:
        staged = Path(argv[argv.index("--out") + 1])
        staged.write_bytes(good_png)
        return StubProcResult(
            0,
            json.dumps({"kind": "image", "response_id": "r_bracket", "status": "completed"}),
        )

    rc_ok = image_gen.main(
        ["--prompt", "Hero diagram", "--ar", "16:9", "--raw-prompt", "--no-verify", "-o", str(bracket_out)],
        runner=FakeGeminiRunner([gen_missing_path_field]),
    )
    assert rc_ok == 0
    assert bracket_out.read_bytes() == good_png
    assert not stale_report.exists(), "stale REJECTED .report.json remained after later VERIFIED pass"




