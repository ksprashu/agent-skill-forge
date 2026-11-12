# Writing Principles — Clarity, Connected Flow, and Humanity

Distilled from Zinsser (*On Writing Well*) and empirical review of real developer prompts and technical readouts. The goal is writing that is clear, concrete, connected, and pleasant to read - never bloated with AI hype, and never chopped into robotic, telegraphic 10-word fragments.

## Core Articles
- **Clarity**: Say what the mechanism does and why it matters. If a trade-off has a hidden catch, state the catch plainly and back it with the exact number or constraint.
- **Connected Flow (Anti-Staccato Rule)**: Do not chop a cause-and-effect thought into two or three clipped 10-word sentences. In technical explanations, dossiers, and reports, join the mechanism and its operational consequence into one smooth, natural sentence (`18–30 words`) using logical connectors (`"because"`, `"whereas"`, `"so that"`, `"which means"`, `"while"`, or `" - "`).
- **Cut Bloat, Keep Connective Tissue**: Deleting throat-clearing (`"In today's rapidly evolving landscape, it is important to note that..."`) makes writing sharper; deleting logical connectors (`"because"`, `"whereas"`, `"so that"`) makes writing sound stoic, mechanical, and fragmented. Strip the fluff, not the grammar that connects ideas.
- **Grounded Humanity**: Write like a senior engineer explaining a system to a peer. Use plain, direct developer language rather than corporate buzzwords or theatrical blog metaphors.

## Practical Rules
- **Pair mechanism with consequence**: Instead of writing *"Context size drives token cost. Request buckets charge one unit per call. Put bulk work on request buckets,"* write: *"Because token-metered buckets scale with context size and thinking tier whereas request buckets charge a flat unit per call regardless of payload, high-volume mechanical loops should always run on a request-metered model."*
- **Prefer active voice and concrete nouns**: Name the system, config file, flag, or quota bucket doing the work.
- **Omit needless wrapper phrases**: Replace `"in order to"` with `"to"`, `"due to the fact that"` with `"because"`, and delete `"it is worth noting that"` or `"it is crucial to remember that"`.
- **Ban theatrical metaphors and AI idioms**: Never use dramatic filler such as *"what the hand gives, the hand takes away"*, *"spins like a centrifuge"*, or *"the difference between a swarm that ships and one that stalls at 3 PM"*. State the engineering reality directly.
- **Match sentence length to the job**:
  - **Technical dossiers, readouts, PRDs, and explanations (`R6` / `R4`)**: Connected 18-to-30-word sentences that carry a complete trade-off or cause-and-effect chain, varied with occasional shorter punchy verdicts.
  - **Code comments and UI labels**: Concise 6-to-15-word factual statements.
  - **Quick internal emails (`R1`)**: 1-4 direct sentences with the answer on line 1.
- **Use tables to carry dense comparisons, and prose to explain why they matter**: Do not repeat every cell of a table in clipped sentences underneath it. Use the paragraph below a table to highlight the deciding trade-off or the hidden bottleneck that the raw numbers imply.

## Framing Technical Dossiers & Readouts (`R6`)
When summarising complex technical systems, benchmarks, or architecture decisions for the user:
1. **Orientation & Verdict Up Front**: Open with 1-2 connected sentences that define the problem space and state the recommended path.
2. **Strengths vs. Hard Limits**: Contrast what each option is genuinely strong at with where it hits a ceiling (`"Option A gives you X, whereas Option B trades Y for Z"`).
3. **The Hidden Catch ("What You Didn't Consider")**: Surface the non-obvious bottleneck, secondary rolling cap, or tail-latency failure mode buried in the spec, backed by the exact math.
