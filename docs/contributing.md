# Editing safely in VS Code

DriftWatch uses a workspace save policy that prevents stale-buffer save
prompts when a formatter, test runner, Git operation, or another editor
updates a tracked file. Auto-save is disabled and an intentional save writes
the current editor buffer to disk.

Avoid editing the same file in multiple VS Code windows or through an editor
and an automated rewrite at the same time. Before switching branches or
applying a large change, save all files and run:

```powershell
git status --short
git diff --check
```

If a change was made by another contributor, fetch and review it before
overwriting the file. The workspace setting is appropriate for this
single-writer development workflow; use VS Code's default conflict prompting
when multiple people or automation edit the same checkout concurrently.
