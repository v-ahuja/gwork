# Git Worktrees — and why gwork exists

## What is a worktree?

A Git worktree is a branch checked out into its own dedicated folder. Instead of switching branches inside a single directory, each branch gets its own isolated working environment.

```
~/worktrees/
  my-repo/
    main/          ← branch: main
    feature-auth/  ← branch: feature/auth
    fix-login-bug/ ← branch: fix/login-bug
```

Every folder is a fully functioning checkout of the same repository. You can open them in separate editor windows, run separate servers, and work on them simultaneously — no stashing, no context switching.

## Why this matters for coding agents

The traditional one-repo-one-folder model forces you to finish or stash what you're doing before switching context. With worktrees, that constraint disappears.

This is especially important now that coding agents (Claude, Codex, Cursor, etc.) can take on entire features autonomously. You can kick off three agents on three branches at the same time and let them run in parallel — each in its own worktree, with no interference.

- Agent A works on `feature/auth` in `~/worktrees/my-repo/feature-auth/`
- Agent B works on `fix/login-bug` in `~/worktrees/my-repo/fix-login-bug/`
- Agent C works on `feature/dashboard` in `~/worktrees/my-repo/feature-dashboard/`

All three run concurrently. No merge conflicts mid-flight, no shared state, no waiting.

---

## Why gwork

Working with worktrees manually involves remembering and running several commands every time.

### Creating a new worktree without gwork

```bash
# 1. Create the worktree
git worktree add ~/worktrees/my-repo/feature-auth -b feature/auth

# 2. cd into it
cd ~/worktrees/my-repo/feature-auth

# 3. Copy over any local config files (.env, secrets, etc.) manually
cp ~/code/my-repo/.env ~/worktrees/my-repo/feature-auth/.env
```

### Switching to an existing worktree without gwork

```bash
# Look up where it lives
git worktree list

# Then cd to it manually
cd ~/worktrees/my-repo/feature-auth
```

### Deleting a worktree without gwork

```bash
# Remove the folder and the Git metadata
git worktree remove ~/worktrees/my-repo/feature-auth

# Optionally delete the branch too
git branch -d feature/auth
```

---

### With gwork

```bash
# Jump to an existing branch worktree (creates it if it doesn't exist)
gwork feature/auth

# Create a new branch in its own worktree
gwork -b feature/new-thing

# Create from a specific base branch
gwork -base main -b feature/from-main

# Delete a worktree (and optionally its branch)
gwork -d feature/auth
```

One command. gwork handles the path resolution, the `git worktree add/remove`, and copies any files listed in `.gw/includes/manual_includes` (like `.env`) automatically. With shell integration installed, it also `cd`s you directly into the result.
