---
name: gsd-phase
description: "workflow | Add / insert / remove / edit a phase (consolidated)"
---

# gsd-phase

Consolidated phase-management skill (post-#2790). Bridge skill: the authoritative
workflow bodies live in this project's GSD core engine (v1.14.0). Pick the file for
the user's intent, read it, and follow it — do not inline it here.

| Intent | Workflow |
|---|---|
| Add a phase | `@.claude/gsd-core/workflows/add-phase.md` |
| Insert a phase | `@.claude/gsd-core/workflows/insert-phase.md` |
| Remove a phase | `@.claude/gsd-core/workflows/remove-phase.md` |
| Edit a phase | `@.claude/gsd-core/workflows/edit-phase.md` |

Runtime helper (resolve from project root):

```bash
node .claude/gsd-core/bin/gsd-tools.cjs <verb> [args]
```
