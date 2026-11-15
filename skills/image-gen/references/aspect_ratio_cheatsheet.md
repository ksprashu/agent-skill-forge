# Aspect Ratio, Size Tier & Mode Reference Cheatsheet

Map visual deliverables to the 14 aspect ratios (`--ar`), 3 output size tiers (`--size`), and 6 craft modes (`--mode`) supported by `scripts/image_gen.py` and `gemini-nano-banana-2.1` / `gemini-3-pro-image`.

---

## 1. All 14 Supported Aspect Ratios (`--ar`)

| `--ar` | Orientation | Typical `1K` Grid (px) | Primary Use Cases & Composition Guidance |
| :---: | :--- | :---: | :--- |
| `1:1` | Square | `1024 x 1024` | `2x2` comic grids, spot icons, avatars, product cards, turnaround medallions |
| `4:3` | Landscape (Standard) | `1152 x 864` | Architecture diagrams, inline documentation figures, slide callouts |
| `3:4` | Portrait (Standard) | `864 x 1152` | Vertical process infographics, character portraits, book-page comic layouts |
| `3:2` | Landscape (Editorial) | `1216 x 832` | Editorial illustrations, photography-style feature headers, 3-beat strips |
| `2:3` | Portrait (Editorial) | `832 x 1216` | Poster art, graphic novel pages, vertical comparison cards |
| `5:4` | Landscape (Compact) | `1120 x 896` | Dense data cards, compact dashboard mockups, balanced two-column diagrams |
| `4:5` | Portrait (Social) | `896 x 1120` | Mobile feed illustrations, portrait feature cards, vertical UI callouts |
| `16:9` | Widescreen | `1344 x 768` | Hero banners, `16:9` presentation slides, widescreen storyboards |
| `9:16` | Vertical / Mobile | `768 x 1344` | Mobile stories, vertical walkthrough screens, portrait storyboards |
| `21:9` | Ultrawide | `1536 x 640` | Cinematic widescreen headers, panoramic environment establishing shots |
| `4:1` | Horizontal Banner | `2048 x 512` | `1x4` horizontal comic strips, ribbon timelines, README section dividers |
| `1:4` | Vertical Strip | `512 x 2048` | 4-step vertical webtoon strips, tall waterfall sequence diagrams |
| `8:1` | Ultra-Ribbon Horizontal | `2048 x 256` | Panoramic header trims, multi-epoch horizontal timeline bars |
| `1:8` | Ultra-Ribbon Vertical | `256 x 2048` | Deep scroll-storytelling sidebars, stacked layer strips |

> **Mechanical Gate Note:** Stage 3 checks actual pixel width/height against `--ar` within a `3.5%` relative tolerance so standard quantised model dimensions (such as `1344 x 768` = `1.75` for `16:9` = `1.7778`) pass cleanly while mismatched orientations (`1:1` returned for `16:9`) fail immediately at `$0` judge cost.

---

## 2. Resolution Tiers (`--size`)

| `--size` | Long-Edge Floor | When to Select |
| :---: | :---: | :--- |
| `1K` | `>= 512 px` | Default for fast single illustrations, icons, mood anchors, and `720p`/`1080p` video keyframes |
| `2K` | `>= 1500 px` | **Auto-enforced** for `--mode comic-grid` and prompts with `>= 2` quoted text labels (`"..."`) or `>= 24` characters of quoted text so speech bubbles and node labels stay sharp |
| `4K` | `>= 3000 px` | Print/A4 dossiers, dense multi-service architecture posters, and zoomable character sheets |

---

## 3. Mode Routing & Reference Limits

- **Reference budget:** Up to `14` images per call via `-r` / `--reference` (`char:`, `style:`, `prop:`, `anchor:`). Passing any reference automatically removes `gemini-3.1-flash-lite-image` from the backup chain so multi-reference grounding stays on `gemini-nano-banana-2.1` and `gemini-3-pro-image`.
- **Sequential manifest aspect ratio:** Keep `--ar` uniform (such as `16:9` or `9:16`) across `--mode timeline` and `--mode comic-panels` runs so downstream consumers receive consistent frame dimensions.
