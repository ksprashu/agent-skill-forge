# Dynamic Judges: Blinded LLM-as-a-Judge Verification

While static verifiers handle deterministic rules (syntax, links, word counts, section headers), qualitative aspects—such as technical depth, logical coherence, tone adherence, and absence of subtle hallucinations—require **Dynamic Verification**.

To eliminate self-assessment bias, dynamic verification is performed by a **Blinded Subagent** launched in a fresh session with **zero past conversation history or execution context**.

---

## 1. The Blinded Judge Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           WORKER CONTEXT (Polluted)                       │
│  - Full conversation history                                              │
│  - Trial-and-error reasoning, intermediate code drafts                   │
│  - Rationalization of decisions & self-bias                               │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      │ Outputs Artifact to Disk
                                      ▼
                      ┌───────────────────────────────┐
                      │    Target Deliverable Artifact │
                      │    (e.g., strategy_doc.md)    │
                      └───────────────┬───────────────┘
                                      │
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         BLINDED JUDGE SUBAGENT                            │
│                                                                           │
│  Inputs:                                                                  │
│    1. Target Deliverable Artifact (Read from Disk)                        │
│    2. Expectation Rubric Schema (rubric.json)                             │
│                                                                           │
│  Isolation Guarantee:                                                     │
│    - ZERO memory of Worker's prompt history or internal thoughts.         │
│    - Treats the artifact purely as a third-party submission.              │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            JUDGE VERDICT LOG                              │
│  - STATUS: PASS / FAIL                                                    │
│  - Score per Rubric Criteria (1-10)                                       │
│  - Pinpointed Defect Delta List (for Worker feedback loop if FAIL)        │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dynamic Rubric Spec Schema (`rubric.json`)

The Orchestrator generates a structured rubric JSON that the Blinded Judge evaluates against:

```json
{
  "rubric_id": "RUBRIC-STRATEGY-01",
  "domain": "business_strategy",
  "criteria": [
    {
      "id": "technical_depth",
      "name": "Technical & Operational Depth",
      "description": "Does the document provide concrete execution steps rather than vague high-level advice?",
      "threshold": 8
    },
    {
      "id": "logical_consistency",
      "name": "Logical Consistency & Risk Realism",
      "description": "Are the proposed risks paired with realistic mitigation plans without self-contradictions?",
      "threshold": 8
    },
    {
      "id": "fact_grounding",
      "name": "Fact Grounding & Citation Quality",
      "description": "Are claims supported by data, research, or cited evidence in the scout bundle?",
      "threshold": 9
    }
  ]
}
```

---

## 3. Blinded Judge Subagent Directive Template (`judge_prompt.md`)

When spawning the Blinded Judge subagent via `invoke_subagent`, pass this clean directive:

```markdown
# BLINDED JUDGE DIRECTIVE: EVALUATION OF [ARTIFACT_NAME]

You are an objective, third-party Quality Audit Judge. Your sole task is to evaluate the deliverable artifact at `[ARTIFACT_PATH]` against the Expectation Rubric defined at `[RUBRIC_PATH]`.

## EXPLICIT CONSTRAINTS:
1. You MUST read the deliverable file from disk using `view_file`.
2. You MUST read the rubric JSON from disk using `view_file`.
3. You have NO prior context about how this document was generated. Evaluate it strictly as an author-blind submission.
4. Do NOT give benefit of the doubt. If a rubric criterion is unmet or partially met below the threshold, fail the criterion.

## REQUIRED OUTPUT FORMAT:
Save your verdict to `.gemini/tasks/[SHORT_ID]/judge_verdict.json`:

```json
{
  "status": "PASS" | "FAIL",
  "overall_score": 8.5,
  "criteria_scores": {
    "technical_depth": 8,
    "logical_consistency": 9,
    "fact_grounding": 8.5
  },
  "defects": [
    {
      "criterion_id": "technical_depth",
      "issue": "Section 3.2 lacks explicit pricing metrics for cloud infrastructure.",
      "remediation": "Add a structured cost breakdown table specifying estimated monthly egress and compute charges."
    }
  ]
}
```
```

---

## 4. Dual-Gate Decision Matrix

| Static Verifier Output | Blinded Judge Verdict | Final Gate Decision | Action |
| :--- | :--- | :--- | :--- |
| **PASS** | **PASS** | **APPROVED** | Advance DAG Node / Sign-off |
| **FAIL** | **PASS** | **REJECTED** | Feed static script error list back to Worker |
| **PASS** | **FAIL** | **REJECTED** | Feed Judge `defects` remediation list back to Worker |
| **FAIL** | **FAIL** | **REJECTED** | Combine static errors + Judge defects into unified Delta Report |
