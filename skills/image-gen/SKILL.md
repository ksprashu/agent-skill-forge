---
name: image-gen
description: Generate technical diagrams, infographics, and UI graphics using Gemini Flash Image. Trigger via /image-gen.
disable-model-invocation: true
---

# Image-Gen: Gemini Flash Image Generation Expert

Generate diagrams, UI graphics, and hero banners using Gemini image models with style consistency.

---

## 🎯 Goal
Synthesize high-fidelity visual assets, charts, and technical diagrams with cohesive art direction.

---

## 📋 Step-by-Step Workflow

1. **Identify Asset Type**: Determine required dimensions (`16:9` hero banner, `4:3` architecture diagram, `1:1` icon).
2. **Generate Primary Asset**:
   ```bash
   python3 scripts/image_gen.py --prompt "Modern cloud infrastructure network topology" --ar "16:9" --output "hero.png"
   ```
3. **Ground Series Style**: For subsequent figures, pass the primary image as a style reference:
   ```bash
   python3 scripts/image_gen.py --prompt "Database replication flow" --references "hero.png" --ar "4:3" --output "fig2.png"
   ```
4. **Iterate & Refine**: Modify images by passing the target file as reference with delta instructions.

---

## 💡 Concrete Example

### Generating Cohesive Documentation Graphics
```bash
# Step 1: Create Hero
python3 scripts/image_gen.py \
  --prompt "Isometric vector diagram of an AI agent coordination engine, clean dark mode aesthetic" \
  --ar "16:9" \
  --output "docs/assets/hero.png"

# Step 2: Create Sub-figure matching hero palette
python3 scripts/image_gen.py \
  --prompt "Close-up diagram of task DAG dispatch queue" \
  --references "docs/assets/hero.png" \
  --ar "4:3" \
  --output "docs/assets/task_dag.png"
```

---

## 🚫 Hard Constraints

*   **NEVER** generate un-referenced follow-up images in a series—always pass previous images as references.
*   **NEVER** hardcode absolute machine file paths into public markdown image embeds.
