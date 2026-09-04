Argument: $ARGUMENTS

This is a thin wrapper around the `path` command. Path is tool-agnostic: everything below works the same from a plain shell, from Aider, or from anything else that can run a command. This file exists only so `/path` is convenient in Claude Code — it must never become the only way to do something.

If `path` is not on `$PATH`, tell the user to symlink it (`ln -s <path-repo>/bin/path ~/.local/bin/path`) rather than guessing at a location.

## Running a mode

The first word of `$ARGUMENTS` is the mode. Run the matching command and show the user its output:

| `$ARGUMENTS` | Command |
|--------------|---------|
| `.` | `path .` |
| `status` | `path status` |
| `close` | `path close` |
| `check` | `path check` |
| `metrics` | `path metrics` |

If `$ARGUMENTS` is empty or matches nothing, run `path --help` and show it.

The CLI does everything deterministic itself: identifiers, frontmatter, status transitions, validation, metrics. **Do not do any of that by hand, and do not edit frontmatter directly** — use `path new task`, `path task`, `path log`, and `path decision`. Hand-editing is how a project drifts out of step with its own tooling.

## Where judgment is still needed

The CLI deliberately stops where facts stop. Two places need a person or an agent to think.

### After `path close`

`path close` writes the session-close entry and regenerates `status.html`. If its output lists tasks with logged issues, read each one's `path.issues` and decide, for each issue, whether a gap in the requirements, the blueprints, or the task itself let it through — or whether it was ordinary execution-time discovery with no documentation gap behind it.

Fill in the entry's **Process Improvement Recommendations**:

- For an issue that traces back to a gap, name the specific document and the specific change that would have prevented it.
- For one that doesn't, say so briefly rather than omitting it.
- If no issues were logged, write that and stop.

Only recommend. Do not edit the requirements, blueprints, or conventions yourself — a change to a source of truth goes through a deliberate update, per the Document Freshness convention, not automatically at close.

Then remind the user to fill in the remaining blanks: Completed This Session, State at Close, Next Session, Blockers.

### After `path check`

`path check` reports facts: a broken link, an inconsistent date, a missing retrospective. It has no opinion about whether the work is any good. When it passes, that means the completion claim is *verifiable* — not that the work is right. The Definition of Done still requires a human review, and the check does not replace it.
