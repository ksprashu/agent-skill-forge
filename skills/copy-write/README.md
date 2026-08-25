# 🦫 copy-write-bara

A collaborative technical writing assistant and blogging companion for developers and Developer Advocates. Features **Profile-Overlay Architecture** to personalize tone, speech cadence, and stylistic nuances without leaking private identity data into shared repositories.

---

## 🚀 Key Highlights & Mandates

> [!IMPORTANT]
> **The Zero-Hallucination Mandate:** Providing misleading technical instructions, non-existent APIs, or phantom configuration flags is a critical failure. All technical claims, configurations, and code snippets must be strictly grounded in verified official documentation or source code.

*   **Profile-Overlay Personalization:** Seamlessly separates open-source baseline templates from private local persona profiles (`references/voice_and_tone.local.md`).
*   **Anti-AI Slop Guardrails:** Banishes AI clichés (*delve*, *testament*, *tapestry*, *demystify*), removes em-dash overuse, and eliminates artificial formatting.
*   **Dual Reference Grounding:** Automatically grounds products with dual links (Landing Page + Official Docs) and concludes articles with structured reference libraries.

---

## 📁 Repository Structure

```
copy-write-bara/
├── SKILL.md                          # Main skill instructions with 3-tier overlay lookup
├── README.md                         # This guide
├── .gitignore                        # Ignores *.local.md private profiles
└── references/
    ├── voice_and_tone.template.md    # Public generic writing style baseline
    ├── golden_examples.template.md   # Public sample articles
    ├── voice_and_tone.local.md       # (Gitignored) Private personalized style
    └── golden_examples.local.md      # (Gitignored) Private writing samples
```

---

## 🛠️ Profile-Overlay Customization

To personalize the assistant for your own writing style:

1. Copy the template to create your private local profile:
   ```bash
   cp references/voice_and_tone.template.md references/voice_and_tone.local.md
   cp references/golden_examples.template.md references/golden_examples.local.md
   ```
2. Edit `references/voice_and_tone.local.md` with your specific phrasing, preferred spelling (Commonwealth vs US), and stylistic rules.
3. Because `*.local.md` is in `.gitignore`, your personal identity and private examples are never committed to public git remotes.

---

## 💬 Usage

Trigger via `/copy-write` or `/copy-write-bara` when drafting, reviewing, or editing articles, blogs, tutorials, and presentation scripts.
