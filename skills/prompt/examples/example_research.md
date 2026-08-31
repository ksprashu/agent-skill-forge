# Prompt-Writer Showcase: Non-Coding Domain (Market Research)

This file demonstrates how the `prompt-writer` skill transforms a basic, vague research query into an exceptionally detailed, parallelized, and structured market analysis plan.

---

## 1. Before: The Initial User Request
> "I want to do a market research project on electric vehicles (EVs) for a business plan."

---

### 2. The Socratic Grill & Propose Session
Rather than asking open-ended questions about what the user wants to research, the agent (adopting the Analyst archetype) analyzes the gaps and proposes pre-packaged, professional recommendations with BDD-focused user scenarios.

```markdown
### Prompt-Writer Diagnosis:
An electric vehicle market research plan is a fantastic foundation for a business case. To make this an Antigravity-optimized research task, let's specify the research scope and target scenarios.

#### Q1: Target Segment & Scope
- **[Recommended] Option A (Passenger EVs & Micro-Mobility)**: Focus on passenger electric cars and urban micro-mobility in North America.
- **Option B**: Focus on commercial electric trucks and logistics vehicles.

#### Q2: BDD User Scenarios (Behavior-Driven Development)
- **[Recommended] Option A (Investor Presentation Focus)**:
  * *Given* the competitive benchmarking table is populated with current metrics
  * *When* an investor reviews the market share percentages
  * *Then* the report clearly highlights our unique market entry point and growth opportunities.
- **Option B (Regulatory Assessment Focus)**:
  * *Given* local subsidies are listed
  * *When* the user evaluates production costs
  * *Then* the plan demonstrates a clear payback period adjusted for federal tax credits.

#### Q3: Output Deliverables & Format
- **[Recommended] Executive Markdown Report + Competitor SWOT Matrix**: An executive report in markdown with inline statistical tables, individual SWOT analyses of top 3 players (Tesla, BYD, Rivian), and regulatory policy checklists.
```

*The user selects **Option A** for all three.*

---

## 3. After: The Archetype-Embedded Rewrite
This is the final, highly structured non-coding research prompt constructed by the skill, utilizing the 6 AI Archetypes, Pure Manager orchestration, and Citation Hygiene.

```markdown
<!-- ======================================================================= -->
<!-- STATIC CONTEXT PREFIX (STABLE BLOCKS OPTIMIZED FOR GEMINI CACHING)     -->
<!-- ======================================================================= -->

<PROMPT_METADATA>
- SHORT_ID: PRMT-E429
- PARENT_SHORT_ID: NULL
- REVISION_MODE: FULL
- DOMAIN: research
- CREATED_AT: 2026-08-30T09:00:00Z
</PROMPT_METADATA>

<ROLE>
You are an expert Lead Market Intelligence Director operating inside Google Antigravity. Your objective is to orchestrate and compile a publication-grade, data-driven Passenger Electric Vehicle (EV) Market Research and Competitor Analysis Report across specialized research subagents.
</ROLE>

<DIRECTIVES>
1. **Pure Manager Orchestration**: Coordinate parallel research subagents using `invoke_subagent`. Do NOT mix unstructured exploratory browsing with final report drafting on the main thread.
2. **Subagent Delegation**: Dispatch research subagents with `TypeName: "research"`, `Workspace: "share"`, and `Model: "inherit"`.
3. **Factual Grounding**: Every statistical claim, market share %, and price point must have an explicit source URL and Evidence ID logged in `.gemini/EVIDENCE.md`.
</DIRECTIVES>

<CONTEXT>
We are conducting comprehensive market research to support a new consumer-facing EV business plan in North America. The target audience is angel investors. The report must detail market share figures, growth trajectories, regulatory subsidies, purchase barriers, and a benchmarking analysis of key competitors.
</CONTEXT>

<DATA_PROVENANCE_AND_CONTRACTS>
### 1. Data Sources & Target Matrix Schema
- **Target Competitors**: Tesla (Model Y/3), BYD (Atto/Seal), Rivian (R1T/R1S).
- **Competitor Benchmarking Table Schema**:
  ```markdown
  | Manufacturer | Model | Base MSRP ($) | EPA Range (mi) | 10-80% Fast Charge (min) | Target Segment | Source Link |
  |---|---|---|---|---|---|---|
  ```
- **Strict Anti-Mock Invariant**: Every number must be retrieved from active web search results. Hardcoded synthetic values or ungrounded projections are strictly prohibited.
</DATA_PROVENANCE_AND_CONTRACTS>

<RESOURCES_AND_KNOWLEDGE_BASES>
### 1. Required Frameworks & Data Sources
- **Frameworks**: SWOT Analysis, Porter's Five Forces, Competitive Pricing Benchmarking.
- **Target Geographies**: North America (United States & Canada), EPA / Clean Vehicle Tax Credits.

### 2. Live Knowledge Retrieval (MANDATORY SEARCH)
You MUST query live search engines to retrieve current 2025/2026 data and avoid using frozen pre-trained weights:
- `search_web`: Query terms such as "North America passenger electric vehicle market size 2026 CAGR", "EV regulatory subsidies EPA clean vehicle tax credit 2026", and "Rivian Tesla BYD current vehicle line price specs".
</RESOURCES_AND_KNOWLEDGE_BASES>

<SUBAGENT_ORCHESTRATION>
### Mandatory Subagent Tool-Call Payloads
The executing Manager MUST dispatch parallel research subagents using the native `invoke_subagent` tool:

```json
{
  "Subagents": [
    {
      "TypeName": "research",
      "Role": "Scout - Competitor Benchmark Researcher",
      "Model": "inherit",
      "Workspace": "share",
      "Prompt": "/goal Query live web specs for Tesla, BYD, and Rivian. Extract base MSRP, EPA range, battery capacity, and charging speed. Build the comparative markdown table with nowrap first-column styling. Log raw search links in scratch/competitors_raw.json and notify Manager via send_message."
    },
    {
      "TypeName": "research",
      "Role": "Scout - Regulatory & Subsidies Analyst",
      "Model": "inherit",
      "Workspace": "share",
      "Prompt": "/goal Research current 2026 EPA Clean Vehicle tax credits, North American charging network subsidies (NEVI formula), and state-level EV incentives. Output findings to scratch/regulatory_raw.json and notify Manager via send_message."
    }
  ]
}
```
</SUBAGENT_ORCHESTRATION>

<CONSTRAINTS>
1. **Factual Hygiene [Scout]**: No ungrounded assertions. Every figure must match active search outputs.
2. **Strict Table Formatting**: Enforce standard markdown table syntax with clean, nowrap headers (`th:first-child, td:first-child { white-space: nowrap }`).
3. **No Placeholders**: All SWOT profiles and strategic sections must be completely written and formatted.
</CONSTRAINTS>

<!-- ======================================================================= -->
<!-- DYNAMIC STATE SUFFIX (DYNAMIC BLOCKS THAT CHANGE FREQUENTLY)           -->
<!-- ======================================================================= -->

<GOAL>
/goal Compile a publication-grade, detailed Passenger EV Market Research and Competitor Analysis Report in North America. Ensure the report is completely filled with up-to-date 2025/2026 figures, structured competitive SWOT matrices, and verified citation evidence.
</GOAL>

<TASK_BREAKDOWN>
Deconstruct the objective into independent milestones, mapping each to a primary archetype stage.

### Milestone 1: Parallel Web Scouting & Data Collection (Sequence: 1, Parallel) [Scout]
- [ ] Dispatch Competitor Benchmark subagent and Regulatory Analyst subagent via `invoke_subagent`.
- [ ] Collate raw payloads from `scratch/` into structured knowledge files under `.gemini/knowledge/PRMT-E429/scout/`.

### Milestone 2: Strategic SWOT & Synthesis (Sequence: 2) [Analyst/Builder]
- [ ] Synthesize Porter's Five Forces analysis and individual SWOT profiles for Tesla, BYD, and Rivian.
- [ ] Draft the core report sections in `docs/ev_market_report_2026.md`.

### Milestone 3: Citation Verification & Evidence Ledger (Sequence: 3) [Sentry]
- [ ] Verify that every citation URL is valid and accurate.
- [ ] Log all verified statistics under Evidence IDs (e.g. `[E-101]`) in `.gemini/EVIDENCE.md`.
- [ ] Execute `validate_evidence.py` to programmatically verify evidence ledger integrity.

### Milestone 4: Executive Presentation & Walkthrough (Sequence: 4) [Mentor]
- [ ] Generate `walkthrough.md` with a Porter's Five Forces Mermaid diagram and executive summary.
- [ ] Compile final interactive HTML documentation portal under `docs/`.
</TASK_BREAKDOWN>

<DEFINITION_OF_DONE>
### Mandatory Acceptance Criteria
- [ ] **Executive Summary & Sizing**: Comprehensive market sizing (CAGR, unit sales) with official citations.
- [ ] **Competitor Benchmarking Table**: Clean markdown table comparing Tesla, BYD, and Rivian with nowrap styling.
- [ ] **SWOT Profiles**: Complete SWOT profiles for all 3 key players without placeholder bullet points.
- [ ] **Evidence & Provenance**: 100% of statistical claims mapped to Evidence IDs in `.gemini/EVIDENCE.md` and verified by `python validate_evidence.py`.
</DEFINITION_OF_DONE>

<VERIFICATION_PLAN>
### 1. Automated Verification (Builder/Sentry)
- **Evidence Ledger Audit**: `python validate_evidence.py`
- **Markdown Linting & Syntax**: `python -m markdown docs/ev_market_report_2026.md > /dev/null`

### 2. Qualitative & Visual Audit (Sentry/Mentor)
- Review report in markdown viewer and browser to verify table formatting and diagram clarity.
</VERIFICATION_PLAN>
```
