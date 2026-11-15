# Narrative Patterns & Storytelling Craft (`chronicle`)

This reference defines the structural and rhetorical patterns that turn technical reports into compelling nonfiction narratives in the tradition of Malcolm Gladwell (*Outliers*, *The Tipping Point*, *Revisionist History*) and Adam Grant (*Originals*, *Think Again*, *Hidden Potential*).

## 1. The Five Signature Moves

### Move 1: The Forensic Cold Open (Zoom In Before You Zoom Out)
Start with a microscope, not a telescope. Instead of opening with "Social media algorithms have changed in 2026," open at a specific timestamp, file path, or human moment:
- *Weak (Report style)*: "X open-sourced its For You ranker in `xai-org/x-algorithm` and assigns different weights to user actions."
- *Strong (Chronicle style)*: "At 06:58 IST on an October morning, if you open the file `home-mixer/params/param.rs` at commit `2f25214` inside X's open-sourced ranking repository, you can see the exact price tag of human attention written in Rust."

### Move 2: The Counterintuitive Hinge ("The Trap of the Obvious")
State the intuitive strategy that 90% of smart practitioners follow, validate why it *feels* right, and then use primary data to show why it fails or backfires.
- *Pattern*: "On the surface, the math looks simple: if you want twice the reach, publish twice as often and optimize for likes. It is the assembly-line theory of authority. There is just one problem. When researchers examined the actual ranking weights..."

### Move 3: Making Methodologies and Caveats Part of the Plot
In standard reports, methodological limits sit in footnotes or appendix tables. In great nonfiction storytelling, the *flaw in the measurement* is part of the story:
- When citing correlational data (such as Buffer's 18.8M X posts or 2M LinkedIn posts), narrate the difference between correlation and causation directly in the story.
- When citing an interested party's survey (such as the Edelman-LinkedIn B2B Thought Leadership studies), invite the reader into the detective room: show what the number says, point out who funded the study, and isolate the durable signal that survives skepticism.

### Move 4: The Contrastive Vignette (Two Builders, Two Paths)
Use grounded, realistic practitioner contrasts (explicitly tagged `[A] Composite Scenario`) to make abstract rules tangible:
- Contrast **The Feed Sprinter** (who chases daily viral hooks, uses AI-generated prose, drops links in comments, and burns 10 hours a week for ephemeral impressions) against **The Compounding Systems Builder** (who runs one deep fortnightly engineering investigation, ships a reproducible GitHub repo, and slices it into native platform artifacts in 175 minutes a week).

### Move 5: The Actionable Field Notebook
Every chapter closes by translating the narrative insight into an immediate engineering or leadership habit:
- **The One-Sentence Principle**: A memorable, quotable law.
- **The Monday Morning Checklist**: Specific tasks with minute budgets and concrete completion gates.
- **The Stop Rule**: What to immediately stop doing, and the trigger that tells you when to pivot or defer.

## 2. Chapter Blueprint Template

## Chapter [N]: [Evocative Narrative Title]
*[Subtitle naming the technical mechanism and the human stake]*

### 1. The Scene / The Puzzle
[2-3 paragraphs opening on a concrete artifact, timestamp, study, or engineering dilemma.]

### 2. The Folklore vs. The Reality
[Unpack why conventional wisdom gets this wrong, then introduce the primary source or dataset.]

### 3. Inside the Mechanism
[Walk through the exact numbers, code weights, architectural boundaries, or empirical findings with inline links and [P]/[D]/[A]/[U] badges. Include a structured table or visual Exhibit where comparisons matter.]

### 4. The Caveat & Where the Rule Flips
[Explicitly address what is unverified [U], correlational, or context-dependent.]

### 5. Chapter Field Notebook (Actionables & To-Dos)
- [ ] **Action 1 ([Time Budget])**: [Concrete step + verification criteria]
- [ ] **Action 2 ([Time Budget])**: [Concrete step + verification criteria]
- **Hard Stop Rule**: [When to pause, cut, or refuse]
