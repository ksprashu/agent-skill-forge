# Design Notes (`skills/image-gen`)

Why `image-gen` is structured around a four-stage stdlib controller and blinded verification loop. Read `SKILL.md` for operational usage.

---

## The Failure Modes This Design Defends Against

The first generation of `skills/image-gen/scripts/image_gen.py` exhibited six compounding defects common in agent-authored media wrappers:

1. **Fragile runtime dependencies (`S1` violation):** Importing `google-genai` and `Pillow` broke execution inside bare agent sandboxes and standalone `npx skills` checkouts whenever third-party wheels were absent or mismatched.
2. **Shut-down model defaults:** Hardcoding retired `3.1-flash` and `-preview` image model IDs (now blocked by `DEPRECATED_MODEL_PREFIXES`) caused immediate runtime failures once preview endpoints retired, while `gemini-3.1-flash-lite-image` remained in multi-reference chains where character grounding silently degraded.
3. **Self-grading generator (`L2` violation):** Passing the generated image back to an image-generation model with a free-text `"Return ONLY YES or NO"` prompt turned verification into decorative self-certification.
4. **Moving-target retries:** When Attempt 1 failed, the script asked an LLM to rewrite the prompt and then verified Attempt 2 against the *rewritten* prompt — allowing retries to pass by dropping the exact user constraint or quoted label that failed.
5. **Silent unverified writes (`S3` violation):** After exhausting retries, the script saved the failed image to `--output` and exited `0`, making downstream workflows treat broken assets as verified deliverables.
6. **Zero binary or fixture tests (`V1`/`V2` violation):** No tests existed to prove that corrupt headers, wrong aspect ratios, undersized comic grids, or contradictory judge responses were rejected.

---

## Architectural Choices

### 1. Zero-SDK Execution Over `gemini-api` CLI (`S1`, `S4`)
`scripts/image_gen.py` uses Python 3.12 standard library modules exclusively (`struct`, `zlib`, `json`, `subprocess`, `argparse`, `hashlib`, `pathlib`) and invokes `gemini-api` with `shell=False` argument vectors. Every subprocess call goes through an injectable `runner` callable so unit tests verify exact CLI vectors deterministically without `unittest.mock` monkeypatching.

Because `gemini-api image --out <path> -o json` rewrites the output file extension when the returned MIME type differs from `--out`, `image_gen.py` always passes `response_format.mime_type` in `--body` and reads the actual written `path` and `response_id` from JSON stdout into a staging path before promoting verified output to `--output`.

### 2. Frozen `VisualRequirementSpec` Before Attempt 1 (`S9`)
Stage 1 compiles an immutable `VisualRequirementSpec` (`spec.json`) and computes its canonical SHA-256 digest (`compute_spec_digest`) before any model runs:
- **Explicit constraints:** Subject, aspect ratio, resolution floor, reference bindings (`char:`, `style:`, `prop:`, `anchor:`), and exact quoted text literals (`extract_quoted_literals` ignores English contractions like `don't` while capturing `"..."` and `'...'` labels).
- **Implicit craft constraints:** Injected deterministically from `--mode` (`comic-grid` panel gutters, reading order, speech bubble contrast, and `>= 2K` floor; `diagram` orthographic hierarchy and zero pseudo-labels; `comic-panels`/`timeline` anchor continuity).
- **Frozen `acceptance_criteria` (`AC-1..N`):** Every retry attempt re-verifies the digest and judges the new candidate against the unmodified `AC-1..N` list. Optional Argon prompt expansion is checked by `validate_expanded_prompt`; if expansion drops any quoted literal, it is discarded in favour of the deterministic compiled prompt.

### 3. Pure-Stdlib Binary Header Gate (`Stage 3`, `$0` Tokens)
Before spending multimodal judge tokens, `inspect_image_header` and `verify_image_mechanical` parse container headers directly from bytes:
- **PNG:** Validates the 8-byte signature, `IHDR` length (`13`), `IHDR` CRC32 checksum via `zlib.crc32`, and big-endian `width`/`height`.
- **JPEG:** Walks `0xFF` marker segments from `SOI` (`0xFFD8`) through `SOF0`–`SOF3`+ (excluding `DHT`, `JPG`, `DAC`) to extract `height` and `width` while rejecting truncated segments.
- **WebP:** Validates `RIFF`/`WEBP` container byte counts and decodes `VP8X` 24-bit canvas dimensions, `VP8 ` lossy keyframe sync codes (`9D 01 2A`), and `VP8L` lossless packed 14-bit dimensions.

Aspect ratios must fall within `3.5%` relative tolerance (matching Nano Banana 2.1 native grid quantisation such as `1344x768` for `16:9`, which sits `1.56%` from `1.7778`), and `2K`/`4K` runs enforce minimum long-edge pixel floors (`>= 1500px` and `>= 3000px`).

### 4. Stateless Blinded Rubric Judge & Python Provenance Validator (`Stage 4`, `S9`)
Stage 4 calls `gemini-4-argon` (failing over to `gemini-4-carbon`, then emergency `gemini-3.8-flash` with an explicit `stderr` warning) via `gemini-api generate --stream=false -o json` with `"store": false` and `"thinking_level": "high"`. The judge never sees generator chain-of-thought, attempt counters, or prior failure rationales.

Crucially, `validate_rubric_verdict` does **not** trust the model's `overall_pass` boolean:
- Every `AC-*` ID from the frozen spec must appear in `criteria_results` with a boolean `passed` and non-empty `observed_evidence` string (missing IDs or empty evidence fail closed).
- `all_passed` is computed in Python across mandatory criteria.
- If `overall_pass` disagrees with the per-criterion truth value (`fixtures/known_bad/contradictory_rubric.json`), `contradiction_detected` is raised and the verdict is rejected.

### 5. Dual-Mode Retry (`edit_turn` vs `regenerate`) & Hard Exit Semantics (`S3`)
- **`edit_turn` (`--previous-interaction-id <response_id>`):** Chosen only when Stage 3 mechanical checks pass, structural `geometry` criteria pass, and `>= 70%` of mandatory criteria already pass — preserving a strong layout while issuing a surgical `"Keep everything else the same. <fix>"` turn.
- **`regenerate`:** Chosen whenever mechanical geometry fails, panel structure fails, or `< 70%` of criteria pass, rebuilding the full prompt with corrective directives while keeping `-i` reference URIs cached via `gemini-api files upload`.
- **Fail-closed exit & loud override (`S3`, §9):** Exhausting `--max-attempts` moves the last candidate to `<stem>.rejected<ext>`, writes `<output>.report.json`, deletes any stale `--output` / `.provenance.json`, and exits `1`. Passing `--allow-unverified` requires a non-empty `--override-reason "<why>"` (`exit 2` if omitted), emits a loud `WARNING` on `stderr`, and records `override_reason` in both `<output>.report.json` and `<output>.provenance.json` (`UNVERIFIED_OVERRIDE`).

---

## Rejected Alternatives

- **Shared `_common/` helper package imported from repo root:** Rejected because `npx skills add` installs `skills/image-gen` standalone outside the monorepo; keeping all logic self-contained inside `scripts/image_gen.py` guarantees zero missing-import failures on standalone installs.
- **Numeric `0-100` visual quality score threshold:** Rejected per `ENGINEERING_STANDARD.md` §3 (`S9`); an aggregate score lets a sharp, well-lit image pass at `85/100` even when a mandatory diagram label is misspelled. Atomic boolean `AC-*` items with cited `observed_evidence` prevent high aesthetic quality from masking factual errors.
