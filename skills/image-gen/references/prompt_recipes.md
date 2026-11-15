# Prompt Recipes & Sequential Craft Patterns

Production prompt patterns for `scripts/image_gen.py` using active Gemini image models (`gemini-nano-banana-2.1` and `gemini-3-pro-image`). Always place exact required labels, titles, or dialogue inside double quotes (`"..."`) so Stage 1 locks them into mandatory `AC-*` verification items.

---

## 1. One-Shot Art Styles (`--mode single --style ...`)

### Editorial Isometric Dark-Mode Hero (`16:9`)
```text
Prompt: Isometric cutaway view of a distributed build cluster routing artifacts through glowing optical conduits into three regional vaults, negative space on the left third for page title.
Flags:  --mode single --style "sleek dark-mode technical editorial, matte slate surfaces, cyan and warm amber rim light" --ar 16:9 --size 2K
```

### Ukiyo-e Woodblock / Botanical Watercolour Illustrations (`3:2` or `4:5`)
```text
Prompt: A solitary lighthouse standing on basalt sea stacks above curling indigo waves at twilight, lantern beam cutting across low mist.
Flags:  --mode single --style "traditional ukiyo-e polychrome woodblock print, visible washi paper grain, Prussian blue and vermilion ink" --ar 3:2
```

```text
Prompt: Cut-section botanical study of an alpine gentian flower showing root system, stem nodes, and open corolla on cream cotton paper.
Flags:  --mode single --style "naturalist watercolour botanical plate, fine sepia ink outlines, soft translucent pigment washes" --ar 4:5
```

---

## 2. Architecture & Technical Diagrams (`--mode diagram`)

### Service Mesh & Policy Boundary Diagram (`4:3` or `16:9`)
```text
Prompt: Flat orthographic architecture diagram on a deep charcoal grid. Left ingress node labeled "Edge Proxy" connects via solid white arrow to central block labeled "Auth Verifier", which branches to "Ledger DB" and "Audit Queue". Clean geometric boxes, generous padding around every label, zero decorative clutter.
Flags:  --mode diagram --style "minimalist dark-mode vector schematic, crisp 2px strokes, high-contrast sans-serif typography" --ar 16:9 --size 2K
```

---

## 3. Character Turnaround Sheets (Anchor Asset for Comics & Video)

Generate a clean turnaround sheet first and pass it via `-r char:<sheet.png>` on every downstream comic grid, panel sequence, or storyboard keyframe:

```text
Prompt: Character turnaround reference sheet on neutral light-grey studio backdrop showing the same engineer from three angles (front view, three-quarter view, side profile): short silver-streaked dark hair, olive utility jacket with brass zipper, round tortoiseshell glasses, carrying a compact field tablet. Consistent proportions and garment details across all three views.
Flags:  --mode single --style "clean ligne claire ink linework with flat cel colours" --ar 16:9 --size 2K -o assets/engineer_anchor.png
```

---

## 4. Single-Image Multi-Panel Comic Grids (`--mode comic-grid`)

`comic-grid` automatically promotes `gemini-3-pro-image`, sets `thinking_level: "high"`, and enforces `--size 2K` minimum so speech bubbles stay sharp.

### Gritty Noir `2x2` Strip (`1:1`)
```text
Prompt: 2x2 four-panel comic grid separated by crisp white gutters, reading left-to-right top-to-bottom. Panel 1 (top-left): rain-streaked server room window at midnight, detective-engineer inspects blinking red rack, caption box reads "02:14 UTC". Panel 2 (top-right): close-up of terminal screen showing a single failing checksum, speech bubble reads "One byte off." Panel 3 (bottom-left): hand unplugging a frayed loopback cable under harsh desk lamp. Panel 4 (bottom-right): rack LEDs turn steady emerald, speech bubble reads "Green across the board."
Flags:  --mode comic-grid --style "gritty noir black-and-white brush ink, heavy chiaroscuro shadows, halftone Midtones" -r char:assets/engineer_anchor.png --ar 1:1
```

### Ligne-Claire `1x4` Horizontal Strip (`4:1`)
```text
Prompt: 1x4 four-panel horizontal comic strip with clean black borders and white gutters. Panel 1: engineer sketches a box diagram on a whiteboard, speech bubble "Spec first." Panel 2: pair-reviewing test cases on a laptop, speech bubble "Red test ready." Panel 3: green checkmarks cascade down wall monitor. Panel 4: calm coffee toast at sunrise window, speech bubble "Shipped clean."
Flags:  --mode comic-grid --style "Franco-Belgian ligne claire comic, uniform black ink outlines, warm pastel flat colours" -r char:assets/engineer_anchor.png --ar 4:1
```

---

## 5. Multi-File Sequential Panels & Timelines (`--manifest`)

Use `--manifest` when generating separate high-resolution frame files (`comic-panels` for multi-image narratives or `timeline` for step-by-step walkthroughs and storyboard manifests). `image_gen.py` verifies Frame `k` before conditioning Frame `k+1` on `[anchor, frame_k]`:

```json
{
  "mode": "timeline",
  "style": "cinematic storyboard, subtle anamorphic lighting, slate and copper palette",
  "aspect_ratio": "16:9",
  "size": "1K",
  "anchor_image": "assets/engineer_anchor.png",
  "frames": [
    {
      "prompt": "Wide establishing shot of the observatory control deck at dusk as telemetry screens wake up",
      "caption": "Phase 1: Cold Start",
      "duration_s": 5
    },
    {
      "prompt": "Medium tracking view as the engineer locks the primary array coordinates on the console",
      "caption": "Phase 2: Alignment",
      "duration_s": 5
    },
    {
      "prompt": "Over-the-shoulder view out the open dome shutter as the calibration beam meets clear night sky",
      "caption": "Phase 3: Lock Confirmed",
      "duration_s": 6
    }
  ]
}
```
