# Codelab Narration & Tone Guide

The tone of the codelab determines its engagement level. Avoid dry, purely technical instructions. We aim for a "Visual-First Storytelling" approach.

## 1. The Persona Approach
A codelab should have a narrator or a central character facing a problem that the technology solves.

**Examples:**
- **Raju the Shopkeeper (The 'Digital Dukaan' style):** A relatable, non-technical business owner trying to modernize. The tone is encouraging, practical, and grounded in real-world business value.
- **Unit 9 & Pixie (The 'Comic Book' style):** A "Digital Noir" aesthetic. Unit 9 is a cyberpunk cat hacker, Pixie is an AI companion. The tone is punchy, slightly cynical, but helpful.
- **The Grumpy Sysadmin:** Reluctant to adopt new tools but won over by automation. Humor comes from cynical observations about traditional IT.
- **Companion Duo (Optional Character Pack):** When `node <skill-dir>/scripts/characters.cjs status` exits `0`, load the user's configured character pack (see `characters.schema.json` and `examples/characters.example/characters.json`, such as a curious builder `"Pip"` paired with a sharp-eyed debugger `"Byte"`). Keep physical appearance descriptors strictly in image-generation prompts rather than tutorial prose. When `characters.cjs status` exits `1` (`tier: neutral`), default to a direct, mascot-free developer voice using `> aside positive` **"Tip:"** and `> aside negative` **"Watch out:"**.

*Action:* Always ask the user what Persona they want to adopt during the Brainstorming phase.

## 2. Engagement Tactics
- **The "Challenge":** Don't just give the answer. Pose a problem and encourage the user to solve it.
  > "Challenge: Write a prompt that asks Gemini to refactor this function to be O(1). Try it yourself before looking at the solution!"
- **The "Ah-ha" Moment:** Explicitly call out when a complex concept clicks.
- **Conversational Transitions:** End steps with a hook to the next.
  > "We've built the engine, but it's sitting in the garage. Let's deploy it to the cloud in the next step."

## 3. Formatting for Readability
- **Show, Don't Tell:** Minimize massive blocks of markdown text. Break explanations into bullet points or multi-panel visual representations if possible.
- **Consistent Callouts:** Use `> aside positive` to highlight "Pro Tips" in the character's voice.

## 4. Content Safety & Theme
If adopting a darker theme (like Digital Noir), ensure a Content Advisory Disclaimer is present at the start of the Codelab. Maintain professionalism even within a humorous persona.