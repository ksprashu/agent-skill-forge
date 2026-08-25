---
name: image-gen
description: Dynamic infographic, diagram, and blog visual asset generator using Gemini Image models. Trigger via `/image-gen` or `/image-gen-expert` when creating or editing visual graphics.
disable-model-invocation: true
---

# Blog & Content Image Generation Expert

This skill provides specialized tools and workflows for generating high-fidelity, dynamic visual assets for content creation (blogs, articles, documentation), ensuring brand/style consistency and visual compliance through automated verification and intelligent model fallback chains.

## Capabilities

1.  **Dynamic Asset Needs Analysis**: Reads text (e.g., a blog draft) and determines the most appropriate visual assets (e.g., a flowchart for a process, a 16:9 hero image for the header, an infographic for statistics).
2.  **High-Fidelity Generation**: Uses `gemini-3.1-flash-image` as the primary workhorse model for state-of-the-art 4K image, diagram, and infographic synthesis.
3.  **Automatic Series Style Grounding**: Automatically reuses previously generated images in a session as reference inputs for subsequent images to guarantee visual cohesion across a whole article or series.
4.  **Image Editing & Sequential Refinement**: Edits existing images by passing the target image as a reference (`--references target.png`) along with modification instructions.
5.  **Intelligent Model Fallback Chain**: Automatically cascades from `gemini-3.1-flash-image` -> `gemini-3.1-flash-lite-image` -> `gemini-3-pro-image` upon API rate limits or model errors.
6.  **Automated Verification**: Uses Gemini Vision to programmatically verify output quality, accuracy, and text legibility (retrying up to 3 times by default).
7.  **Custom Aspect Ratios**: Supports explicit aspect ratio configuration (`16:9`, `1:1`, `4:3`, `3:4`, `9:16`).

---

## 🎨 Automatic Reference Usage Patterns

### Pattern A: Generating a Series of Images for an Article / Blog
When creating multiple visual assets for a single document or blog post:
1. **Generate Asset #1** (e.g., Hero image `hero.png`).
2. **Auto-Ground Subsequent Assets**: For Assets #2, #3, etc. (e.g., `flowchart.png`, `infographic.png`), **automatically pass `--references "hero.png"`** to `scripts/image_gen.py`.
3. **Outcome**: Gemini matches the visual style, color scheme, lighting, and line weight of `hero.png` across every figure in the entire article.

### Pattern B: Editing & Modifying an Existing Image
When updating or tweaking an existing graphic (e.g., *"Add a database node to `arch.png`"*, *"Change the theme of `banner.png` to dark mode"*):
1. **Pass the Target Image**: Always pass the existing file via `--references "path/to/existing.png"`.
2. **Describe the Delta**: Specify what to keep and what to change in `--prompt`.
3. **Outcome**: Gemini preserves the composition and visual structure of the reference while making the requested modification.

### Pattern C: Workspace Brand Auto-Detection
If any reference image exists in `assets/` (e.g., `assets/brand_style.png`), the agent automatically attaches it as a reference for all new image generations in the project.

---

## Prerequisites

*   **API Key**: Ensure `GOOGLE_API_KEY` is set in the environment. If missing, the agent will securely prompt you for it using the `ask_user` tool during the session.
*   **Dependencies**: The bundled script requires `google-genai` and `Pillow` (PIL).

## Usage

### Generating & Editing Assets

**1. Standalone Hero Image:**
```bash
python scripts/image_gen.py --prompt "A cinematic, wide-shot hero image representing modern cloud architecture, corporate blue tones" --ar "16:9" --output "hero.png"
```

**2. Auto-Grounded Series Image (Passing Hero as Reference):**
```bash
python scripts/image_gen.py --prompt "An architecture diagram showing microservices connected to a gateway" --references "hero.png" --ar "4:3" --output "architecture.png"
```

**3. Editing an Existing Image:**
```bash
python scripts/image_gen.py --prompt "Based on the reference diagram, add a Redis caching service block next to the database" --references "architecture.png" --ar "4:3" --output "architecture_v2.png"
```

### Script Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--prompt` | **Required.** The text description or edit instructions. | N/A |
| `--references` | Comma-separated paths to reference images for series consistency or image editing. | None |
| `--ar` | Aspect ratio (`16:9`, `1:1`, `4:3`, `3:2`, `2:3`, `3:4`, `9:16`). | `1:1` |
| `--output` | Filename for the generated image. | `output.png` |
| `--max-attempts` | Maximum attempts for generate-verify-refine loop. | `3` |
| `--no-verify` | Skip the automated verification step. | False |
| `--api-key` | Optional override for `GOOGLE_API_KEY`. | None |
| `--model` | Primary image generation model. | `gemini-3.1-flash-image` |
| `--verifier-model` | Model used for automated verification. | `gemini-3.1-flash-image` |

---

## 🤖 Agent Operational Instructions

As an AI Agent utilizing this skill, enforce these automatic rules:

### Rule 1: Automatic Series Consistency
When generating multiple visual assets for a single user prompt or blog post:
- Save the first generated image (e.g., `hero.png`).
- For every subsequent image in the same series, **automatically pass `--references "hero.png"`** to `scripts/image_gen.py`.

### Rule 2: Automatic Image Editing / Iteration
When the user asks to edit, revise, or update an existing image:
- Locate the existing image file.
- Automatically execute `scripts/image_gen.py` with `--references "path/to/existing.png"`.

### Rule 3: Repository Brand Detection
Check if `assets/` contains any style reference image. If found, include it in `--references` by default.

### Rule 4: Model Selection & Fallback Chain
- Primary: `gemini-3.1-flash-image`
- Secondary: `gemini-3.1-flash-lite-image` (automatically bypassed when `--references` are present, as flash-lite is not optimized for multi-reference grounding).
- Tertiary: `gemini-3-pro-image` / `gemini-3-pro-image-preview`.
