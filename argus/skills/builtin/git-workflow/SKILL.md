---
name: git-workflow
description: Safe Git operations and commit discipline
triggers: git, commit, branch, merge, rebase, diff, status
---

# Git Workflow Skill

## Workflow

1. Inspect status and diff before staging
2. Stage only relevant files
3. Write a clear commit message
4. Request user approval for write operations
5. Verify commit succeeded

## Rules

- Never stage secrets or generated artifacts.
- Never force push without explicit user request.
- Always show diff before committing.
