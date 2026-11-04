# Changelog

## 2026-10-29
- Made unslop persona-neutral: removed `references/voice_and_tone.md` and every persona reference. Personal voice moved to the new `voice-register` skill (#17).
- Workflow is now detect → subtract → clarify → optional voice overlay → verify → output.
- Renamed `examples/voice-samples.md` to `examples/samples.md`; they were unslop-only rewrites.
- Added a persona-neutral eval; "rewrite in my voice" now routes to `voice-register`.

## 2026-10-19
- Refined writing principles and examples based on user voice feedback.
- Preserve short contextual framing and concrete value terms (measurable, best practice, architecture names) when they add meaning.
- Updated voice-samples.md to match preferred rewrites.
- Core workflow: detect AI smells → subtract → rewrite in voice using Zinsser-inspired principles → verify facts.
- Added voice_and_tone.md (from existing persona extracts), writing-principles.md, and ai-smells.md.
- Default application to all human-readable text outputs (prose, comments, docs, analyses).
