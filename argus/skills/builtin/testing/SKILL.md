---
name: testing
description: Test-driven verification and quality gates
triggers: test, pytest, cargo test, jest, coverage, failing test
---

# Testing Skill

## Workflow

1. Identify the test runner from project context
2. Run the relevant test suite
3. Read failing test output
4. Fix the underlying issue
5. Re-run tests until green

## Rules

- Prefer the project's native test runner.
- Run tests after every change.
- Do not ignore failing tests without explicit user request.
