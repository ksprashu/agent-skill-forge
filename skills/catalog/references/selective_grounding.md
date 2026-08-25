# Selective RAG Context Grounding via OKF Index

To prevent prompt-token bloat and ensure fast execution, the Open Knowledge Format (OKF) implements **Selective Context Grounding (On-Demand RAG)**.

---

## 1. The Selective Hydration Lifecycle

Instead of ingesting the entire `.gemini/knowledge/` bundle into agent memory:

```
+---------------------------------------------------------------------------------+
|                        SELECTIVE RAG HYDRATION FLOW                             |
+---------------------------------------------------------------------------------+
|                                                                                 |
|  1. Index Inspection: Read `.gemini/knowledge/index.md`                         |
|  2. Target Slicing: Identify matching Concept IDs needed for current task node   |
|  3. On-Demand View: Ingest only target concept files via `view_file`            |
|  4. Execution & Promotion: Create/update concept files only upon milestone PASS  |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

## 2. Concept Index Structure (`.gemini/knowledge/index.md`)

```markdown
# Open Knowledge Format (OKF) Bundle Index

| Concept ID | Concept Title | Type | File Path | Grounding Scope |
| :--- | :--- | :--- | :--- | :--- |
| `CONCEPT-AUTH` | Multi-Factor Auth Flow | Architecture | `.gemini/knowledge/auth_flow.md` | Session security & JWT |
| `CONCEPT-DB` | PostgreSQL Schema | Schema | `.gemini/knowledge/db_schema.md` | Data persistence & ORM |
```

---

## 3. Verification Protocol

Validate all concept documents using the native deterministic verifier:

```bash
python3 skills/knowledge-catalog/scripts/verify_okf.py .gemini/knowledge/auth_flow.md
```
