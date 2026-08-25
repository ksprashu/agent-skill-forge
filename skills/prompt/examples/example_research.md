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
This is the final, highly structured non-coding research prompt constructed by the skill, utilizing the 6 AI Archetypes and Citation Hygiene.

```markdown
<ROLE>
You are an expert Lead Market Intelligence Analyst operating inside Google Antigravity. Your objective is to compile a publication-grade, data-driven Passenger Electric Vehicle (EV) Market Research and Competitor Analysis Report, operating under the 6 AI Archetypes.
</ROLE>

<CONTEXT>
We are conducting comprehensive market research to support a new consumer-facing EV business plan in North America. The target audience is angel investors. The report must detail market share figures, growth trajectories, regulatory subsidies, purchase barriers, and a benchmarking analysis of key competitors.
</CONTEXT>

<RESOURCES_AND_KNOWLEDGE_BASES>
### 1. Required Methodologies & Data Sources
- **Frameworks**: SWOT Analysis, Porter's Five Forces, Competitive Pricing Benchmarking.
- **Target Competitors**: Tesla, BYD, Rivian.

### 2. Live Knowledge Retrieval (MANDATORY SCHOLAR SEARCH)
You MUST query live search engines to retrieve 2025/2026 data and avoid using frozen pre-trained weights:
- **search_web**: Query search terms such as "North America passenger electric vehicle market size 2026 CAGR", "EV regulatory subsidies EPA clean vehicle tax credit 2026", and "Rivian Tesla BYD current vehicle line price specs".
</RESOURCES_AND_KNOWLEDGE_BASES>

<GOAL>
/goal Compile a publication-grade, detailed Passenger EV Market Research and Competitor Analysis Report in North America. Ensure the report is completely filled with up-to-date 2025/2026 figures and structured competitive SWOT matrices.

### Definition of Done (Exit Criteria)
- [ ] **Executive Summary**: A concise, investor-ready overview of the EV market landscape.
- [ ] **Pillar 1 - Sizing & Subsidies**: Clear market share percentages, CAGR growth rates, and details on local federal tax credits.
- [ ] **Pillar 2 - Purchase Barriers**: Data-supported breakdown of range anxiety, battery pricing premiums, and local charging station growth rates.
- [ ] **Pillar 3 - Competitor Benchmarking Matrix**: A markdown table comparing Tesla, BYD, and Rivian across base price, EPA range, and charging speed.
- [ ] **Citation Hygiene [Sentry]**: All statistical claims, market shares, and specifications must have explicit source citations linked to an Evidence ID in `.gemini/EVIDENCE.md`.
- [ ] **No Placeholders**: Every SWOT profile and table cell must be completely written and polished. Zero "TBD" or mock figures.
</GOAL>

<TASK_BREAKDOWN>
Deconstruct the objective into independent milestones, mapping each to a primary archetype stage.

### Milestone 1: Setup, Baseline Research & Sizing (Sequence: 1) [Scout]
- [ ] Query live search engines to extract market shares, growth rates, and regulatory tax credits.
- [ ] Draft Section 1 (Market Sizing and Policy Subsidies).
- [ ] Record verification evidence as `[E-101]` in `.gemini/EVIDENCE.md`.

### Milestone 2: Competitor Benchmarking (Sequence: 2, Parallel-Eligible) [Builder]
- [ ] Benchmark Tesla, BYD, and Rivian vehicle portfolios using live specifications.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Builder archetype:
  ```python
  Role: "Builder - Competitor Researcher"
  Prompt: "Search live web specs for Tesla (Model Y/3), BYD (Atto/Seal), and Rivian (R1T/R1S). Benchmark base pricing, EPA range, charging times, and key software features. Structure findings in a comparative markdown table with the first column as nowrap."
  ```

### Milestone 3: SWOT & Purchase Barrier Analysis (Sequence: 2, Parallel-Eligible) [Builder]
- [ ] Research consumer purchase hurdles (pricing, battery health, range anxiety).
- [ ] Formulate detailed SWOT profiles for the top 3 manufacturers.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Builder archetype:
  ```python
  Role: "Builder - Strategic Analyst"
  Prompt: "Conduct live research on North American charging infrastructure and consumer purchase hurdles (pricing, Battery Health, range anxiety). Write separate, high-fidelity SWOT profiles for Tesla, BYD, and Rivian."
  ```

### Milestone 4: Synthesis & Fact Verification (Sequence: 3) [Sentry]
- [ ] Merge report sections from parallel research subagents.
- [ ] Verify that every URL citation is active, correct, and matches historical evidence.
- [ ] Compile all citation links, logging them under Evidence IDs inside `.gemini/EVIDENCE.md`.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Sentry archetype:
  ```python
  Role: "Sentry - Fact Sentry"
  Prompt: "Review the merged report. Ensure there are no fabricated statistics. Cross-check all prices, vehicle models, and CAGR percentages against live search outputs. Log evidence under Evidence IDs in .gemini/EVIDENCE.md."
  ```

### Milestone 5: Executive Presentation & Mentoring (Sequence: 4) [Mentor]
- [ ] Write a walkthrough documenting key market takeaways and strategic recommendations.
- [ ] Create a Mermaid.js diagram illustrating the market's Porter's Five Forces forces.
- [ ] Outline 1-2 strategic "sandbox exercises" (e.g., modeling a potential market shock) for stakeholder analysis.
</TASK_BREAKDOWN>

<CONSTRAINTS>
1.  **Factual Hygiene [Scout]**: No ungrounded assertions. Every figure must match active search outputs.
2.  **Strict Table Formatting**: Enforce standard markdown table syntax with clean, nowrap headers.
3.  **No Placeholders**: All SWOT profiles and strategic sections must be completely written and formatted.
</CONSTRAINTS>

<VERIFICATION_PLAN>
### 1. Source & Citation Cross-Checking (Builder/Sentry)
- Verify all citation links in the final report.

### 2. Manual and Visual Auditing (Sentry/Mentor)
- Review report rendering in a markdown viewer to ensure the benchmarking table displays cleanly without awkward line wraps.
</VERIFICATION_PLAN>
```
