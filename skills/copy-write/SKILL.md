---
name: copy-write
description: Draft technical prose using profile-overlay voice personalization. Trigger via /copy-write.
disable-model-invocation: true
---

# Copy-Write: Technical Prose & Voice Overlay

Draft and refine technical articles, documentation, and blog posts with personalized style overlays.

---

## 🎯 Goal
Produce grounded technical writing matching human cadence and style rules without AI clichés.

---

## 📋 Step-by-Step Workflow

1. **Resolve Persona Profile (3-Tier Resolution)**:
   - Priority 1: `references/voice_and_tone.local.md` (local machine override)
   - Priority 2: `~/.gemini/personas/default/voice_and_tone.md` (user home profile)
   - Priority 3: `references/voice_and_tone.template.md` (public base template)
2. **Ground Technical Claims**: Look up official doc links before explaining APIs or commands.
3. **Draft Outline & Structure**: Propose section headings and target takeaways.
4. **Draft Prose with Anti-AI Rules**:
   - Banish AI clichés (*delve*, *testament*, *tapestry*, *demystify*).
   - Banish em-dashes (`—`) in favor of clean commas or periods.
   - Use dual product links: `[Product](landing) ([Docs](docs))`.
5. **Add References Section**: Conclude with `## 📚 References & Further Reading`.

---

## 💡 Concrete Example

### Fixture: Article Section
```markdown
# Building Low-Latency Microservices

Deploying services on [Google Cloud Run](https://cloud.google.com/run) ([Docs](https://cloud.google.com/run/docs)) gives you automatic concurrency scaling with zero infrastructure management overhead.

## Key Considerations
* Configure minimum instances (`--min-instances=1`) to eliminate cold start latency.
* Use SQLite WAL mode for local in-memory caching.

## 📚 References & Further Reading
* [Cloud Run Concurrency Guide](https://cloud.google.com/run/docs/about-instance-scaling)
```

---

## 🚫 Hard Constraints

*   **NEVER** use AI filler words (*delve*, *testament*, *tapestry*, *furthermore*).
*   **NEVER** invent CLI flags or API parameters without official doc grounding.
*   **NEVER** commit private `.local.md` files to public git branches.
