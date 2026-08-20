---
name: debugging
description: Systematic bug investigation and fix workflow
triggers: bug, crash, error, fail, traceback, panic, fix, debug
---

# Debugging Skill

## Workflow

1. Reproduce the failure
2. Locate the failing code
3. Form a hypothesis
4. Apply a minimal fix
5. Verify with tests

## Rules

- Always read the failing file before editing.
- Use grep to find related error messages.
- Run the smallest relevant test first.
- Do not change unrelated code.
