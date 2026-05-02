---
description: Delete a file or folder inside the OpenRepose repo with directory-climb and root-deletion guards.
argument-hint: <relative-path-from-repo-root>
allowed-tools: Bash, Read, Glob
---

# /safe-delete

Delete a file or folder inside the OpenRepose repo through a guarded path. Refuses anything that resolves outside the repo root.

## Why this exists

Past disasters: wrong git tooling and accidental directory-climbing deleted entire repos and an entire disk. Manual `rm` / `Remove-Item` / `del` on tracked files or repo folders is forbidden by `.gov/AGENTS.md` "Deletion Protocol". This command is the only sanctioned deletion path on the Claude side.

## Argument

`$ARGUMENTS` — a path RELATIVE to the repo root. Examples:

- `target/test-artifacts/WP-I1-001/` — clean a WP's test artifact directory.
- `outputs/.runtime/snapshots/20260502-172405-044_3d_viewport.png` — remove one snapshot.
- `.gov/workflow/workpackets/WP-I1-099-bad-draft.md` — discard a draft WP.

## Required behavior when this command runs

1. **Refuse absolute paths.** If `$ARGUMENTS` starts with `/`, `\`, a drive letter (`A:`-`Z:`), or contains `..`, refuse and explain. The argument MUST be a relative path that does not escape the repo root.
2. **Refuse parent-of-repo and repo root.** Forbidden literal targets: `.`, `./`, `..`, `../`, the repo root path, `.git`, `.gov`, `.product`, `scripts`. Asking to delete `.gov` or `.product` wholesale is always a mistake; refuse and ask the operator to name a narrower target.
3. **Refuse blank-space or empty argument.** If `$ARGUMENTS` is empty or whitespace, refuse.
4. **Resolve and verify containment.** Compute the absolute path of `$ARGUMENTS` joined to the current repo root (use `git rev-parse --show-toplevel` to get the root). Verify the resolved path:
   - Starts with the repo root.
   - Is not equal to the repo root.
   - Exists.
5. **Show the operator the resolved path, the size, and the file count BEFORE deleting.** Use `Get-ChildItem -LiteralPath <path> -Recurse -Force | Measure-Object Length -Sum`. Print `path:`, `entries:`, `total_size_bytes:`, `last_write:`.
6. **Ask the operator to confirm with the literal token `DELETE`.** No other token proceeds. If the operator does not type exactly `DELETE` (case-sensitive), abort.
7. **Log to `target/safe-delete-log/<YYYYMMDD-HHMMSS>.log`.** Record: timestamp, resolved path, size, entry count, operator confirmation token. Then run `Remove-Item -LiteralPath <path> -Recurse -Force`. Then re-check existence and report success or the underlying error.
8. **Never run any of**: `Remove-Item -Path <root>`, `Remove-Item -Path *`, `cd ..`, `Set-Location ..`, `Get-Location` followed by `Remove-Item` of a parent. Never expand globs that could touch outside the supplied path.

## Output format

```
[safe-delete] root:        <repo root>
[safe-delete] requested:   $ARGUMENTS
[safe-delete] resolved:    <absolute path>
[safe-delete] entries:     <N>
[safe-delete] total_bytes: <B>
[safe-delete] last_write:  <ISO>
[safe-delete] log:         target/safe-delete-log/<file>.log

Type DELETE to proceed (anything else aborts):
```

After confirmation:

```
[safe-delete] OK   removed: <path> entries=<N> bytes=<B>
```

Or on refusal / abort:

```
[safe-delete] ERR  refused: <reason>
```

## When to refuse outright

- The resolved path equals the repo root.
- The resolved path is a parent of the repo root.
- The resolved path is `.git/` or anything inside it (use git itself for repo surgery).
- `$ARGUMENTS` contains `..`, an absolute prefix, a drive letter, or a UNC path (`\\server\share`).
- The supplied target does not exist (nothing to delete; the operator probably mistyped).

If the operator insists on deleting outside the repo, refuse and tell them to do it by hand consciously.
