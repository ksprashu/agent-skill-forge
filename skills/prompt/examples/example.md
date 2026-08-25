# Prompt-Writer Showcase: Before, Grill, and After

This file showcases how the `prompt-writer` skill transforms a vague, single-sentence request into an exceptionally clear, highly parallelized, and technically sound Antigravity task.

---

## 1. Before: The Initial User Request
> "I want to build a simple web dashboard to query BigQuery and show sales charts using React."

---

## 2. The Socratic Grill & Propose Session
Instead of leaving the user to figure out the technical architecture or asking open-ended questions, the agent (adopting the Analyst archetype) analyzes the gaps and proposes pre-packaged recommendations with BDD-focused user scenarios.

```markdown
### Prompt-Writer Diagnosis:
Your sales dashboard concept is solid! To write the optimal prompt, let's align on a few technical and design decisions. I have formulated default professional recommendations below.

#### Q1: Build Framework & Setup
- **[Recommended] Option A (Sleek & Fast)**: React 19 bootstrapped with **Vite**, utilizing **Vanilla CSS** with a custom-themed design system. Extremely fast load times.
- **Option B**: React 19 with **Next.js App Router** (React Server Components), ideal if you plan to write serverless API endpoints.

#### Q2: BDD User Scenarios (Behavior-Driven Development)
- **[Recommended] Option A (Interactive Chart Focus)**:
  * *Given* the database contains valid sales records
  * *When* the user selects a date range on the dashboard
  * *Then* the sales line chart immediately updates with smooth gradient transitions.
- **Option B (Tabular Export Focus)**:
  * *Given* loaded records
  * *When* the user clicks "Export CSV"
  * *Then* the app compiles and downloads the formatted table data without reloading the page.

#### Q3: BigQuery Authentication & Schema
- **[Recommended] Python Middleware + Node Frontend**: A lightweight FastAPI proxy utilizing the official `google-cloud-bigquery` library, communicating with the React client.
```

*The user selects **Option A** for all three.*

---

## 3. After: The Archetype-Embedded Rewrite
This is the final, highly structured prompt output by the skill, engineered to leverage the 6 AI Archetypes and Citation Hygiene.

```markdown
<ROLE>
You are an expert Lead Software Engineer and Architect operating inside Google Antigravity. Your goal is to build a premium, fast, and visually stunning BigQuery Sales Dashboard using React (Vite) and FastAPI, managing the pipeline under the 6 AI Archetypes.
</ROLE>

<CONTEXT>
We are building a Sales Dashboard from scratch. The system consists of a lightweight Python FastAPI data API that queries sales records from BigQuery and a React (Vite) frontend that displays interactive sales visualizations (Recharts) using custom glassmorphism styles.
</CONTEXT>

<RESOURCES_AND_KNOWLEDGE_BASES>
### 1. Technology Stack
- **Frontend**: React 19, Vite, Recharts, Vanilla CSS (Frosted glass effects, Inter typography, HSL CSS variables).
- **Backend**: Python 3.11, FastAPI, `google-cloud-bigquery` client SDK.

### 2. Live Knowledge Retrieval (MANDATORY SCHOLAR MCP)
You MUST query live specifications to guarantee correct syntax and avoid legacy API speculation:
- `developer-knowledge`: Run `search_documents` or `answer_query` for "google-cloud-bigquery python client query" to get the exact async client usage and authentication setup.
- `content7`: Run `query-docs` for "recharts responsive container api" to ensure proper chart responsiveness.
</RESOURCES_AND_KNOWLEDGE_BASES>

<GOAL>
/goal Build a fully functional, premium React Sales Dashboard powered by a FastAPI BigQuery proxy. Ensure all components are written with production-ready glassmorphism styles and interactive charts.

### Definition of Done (Exit Criteria)
- [ ] Backend API: Healthy, documented FastAPI service with a `/api/sales` endpoint returning monthly metrics.
- [ ] Frontend UI: Frosted glass sidebar, responsive chart card (Recharts), and a detailed sales datatable.
- [ ] Layout Safeguard: First column of the data table must enforce `white-space: nowrap !important` to prevent broken words.
- [ ] Citation Hygiene [Sentry]: All verification test runs and build confirmations must be logged under Evidence IDs (e.g. `[E-101]`) in `.gemini/EVIDENCE.md`.
- [ ] No Placeholders: Zero stub code, "TBD", or un-implemented endpoints.
</GOAL>

<TASK_BREAKDOWN>
Deconstruct the objective into independent milestones, mapping each to a primary archetype stage.

### Milestone 1: Environment Grounding & Schema Verification (Sequence: 1) [Scout]
- [ ] Query `developer-knowledge` to extract the latest async client syntax for BigQuery.
- [ ] Create `backend/db_client.py` and write a baseline connectivity check. Do not mock API methods.
- [ ] Record verification evidence as `[E-101]` in `.gemini/EVIDENCE.md`.

### Milestone 2: FastAPI Proxy API Development (Sequence: 2, Parallel-Eligible) [Builder]
- [ ] Create the FastAPI application inside `backend/main.py` and implement the `/api/sales` route.
- [ ] Write pytest endpoints inside `backend/tests/` to validate output formats.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Builder archetype:
  ```python
  Role: "Builder - API Developer"
  Prompt: "Write the FastAPI service in backend/main.py. Integrate the BigQuery client from db_client.py. Write pytest endpoints. Enforce local sandbox isolation and mock client queries for test runs. Max iterations: 3."
  ```

### Milestone 3: React Vite & Glassmorphism Frontend (Sequence: 2, Parallel-Eligible) [Builder]
- [ ] Bootstrap the React application in `frontend/` using Vite.
- [ ] Create `index.css` defining glassmorphism tokens, CSS variables, and Outfit typography.
- [ ] Build the sidebar and line chart widgets using Recharts.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Builder archetype:
  ```python
  Role: "Builder - Frontend Developer"
  Prompt: "Bootstrap Vite React in frontend/. Create index.css with glassmorphism frosted variables. Build the responsive sidebar, chart cards (Recharts), and datatable. Enforce nowrap on the first column code blocks. Max iterations: 3."
  ```

### Milestone 4: Security & Quality Audit (Sequence: 3) [Sentry]
- [ ] Audit code files for credentials safety, license compliance, and perfect tag closures.
- [ ] Run `pytest` on the backend and `npm run build` on the frontend.
- [ ] Compile all build hashes and test successes, logging them under Evidence IDs inside `.gemini/EVIDENCE.md`.
- *Parallel Execution*: Invoke a specialized subagent (`invoke_subagent`) adopting the Sentry archetype:
  ```python
  Role: "Sentry - Quality & Security Sentry"
  Prompt: "Verify frontend tag closures to prevent blank pages. Inspect backend routes for injection safety. Verify all build outputs and write complete logs with Evidence IDs into .gemini/EVIDENCE.md."
  ```

### Milestone 5: Walkthrough & Handoff (Sequence: 4) [Mentor]
- [ ] Write a complete `walkthrough.md` documenting the system architecture using Mermaid.js.
- [ ] Detail design decisions (such as Separations of Concerns).
- [ ] Provide 1-2 sandbox challenges (e.g., adding an export CSV function) for developer learning.
</TASK_BREAKDOWN>

<CONSTRAINTS>
1.  **Factual Hygiene [Scout]**: Never invent library endpoints; verify syntax via MCP search.
2.  **Sandbox Isolation [Builder]**: Write and test components within distinct task subdirectories.
3.  **Perfect Symmetry**: No unbalanced tags to ensure zero page-rendering breakages.
4.  **No Placeholders**: All deliverables must be fully implemented, functional, and documented.
</CONSTRAINTS>

<VERIFICATION_PLAN>
### 1. Automated Verification (Builder/Sentry)
- Backend: Run `pytest backend/tests/`
- Frontend: Run `npm run build` in `frontend/`

### 2. Manual Visual Audit (Sentry/Mentor)
- Launch a browser subagent (`browser_subagent`) to open the dashboard locally:
  - Check that charts update gracefully upon date selection.
  - Verify that frosted glass backdrop-filters render correctly.
  - Inspect table structures to ensure codes/keys do not wrap onto multiple lines.
</VERIFICATION_PLAN>
```
