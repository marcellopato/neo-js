# Worktree orchestration

Use project-configured worktree helpers when available. Otherwise stay in read-only
planning until the user confirms a worktree strategy. Split only genuinely independent
tasks, record dependencies and path ownership, and do not switch branches or create
worktrees implicitly.

This package has no CLI runtime scheduler. A skill may execute authorized worktrees while
following this lifecycle:

```text
PLAN → CREATE → ASSIGN → EXECUTE → COLLECT → HANDOFF → CLEANUP
```

```text
tasks
  → dependencies
  → DAG (must be acyclic)
  → waves (independent tasks in a wave)
  → parallel worktrees only with explicit user authorization
```

`saf-implement-multi` already requires an acyclic graph and isolation. Waves group
independent tasks. Parallel worktrees are allowed only with explicit user authorization.
Do not create worktrees, switch branches, or run a multi-task execution without explicit
authorization. Only clean up worktrees created by this execution, and stop rather than delete
when they contain uncommitted or unknown state. Commit, merge, cherry-pick, and push remain
separately authorized.
