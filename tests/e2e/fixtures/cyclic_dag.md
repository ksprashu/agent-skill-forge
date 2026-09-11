# Declarative DAG: Cyclic Dependency Error

Topology: cyclic
Integrity Mode: development

---

## 📋 Task Graph

| ID | Task Name | Mode | Depends On | Inputs | Outputs | Gate | Status |
|---|---|---|---|---|---|---|---|
| `node_a` | Task Node A | series | node_c | none | out_a.txt | none | PENDING |
| `node_b` | Task Node B | series | node_a | out_a.txt | out_b.txt | none | PENDING |
| `node_c` | Task Node C | series | node_b | out_b.txt | out_c.txt | none | PENDING |
