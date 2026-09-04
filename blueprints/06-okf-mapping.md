---
type: Blueprint
title: OKF Mapping
description: How Little Collie Path documents map onto the Open Knowledge Format, and where Path extends it.
tags: [okf, schema, conventions]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — OKF Mapping

Every Path document is an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) concept. This blueprint records what OKF requires, what Path adds on top, and why each choice was made.

## What OKF Actually Requires

OKF v0.1 (Google Cloud, June 2026) is deliberately tiny. Reading the specification rather than the commentary around it, a bundle is a directory of UTF-8 Markdown files, and each concept file is YAML frontmatter followed by a Markdown body.

| Field | Status in OKF |
|-------|---------------|
| `type` | **Required.** A short string naming the kind of concept. |
| `title` | Recommended. Human-readable display name. |
| `description` | Recommended. Single-sentence summary. |
| `resource` | Recommended. A URI identifying the underlying asset. |
| `tags` | Recommended. A YAML list of strings. |
| `timestamp` | Recommended. ISO 8601 datetime of last modification. |

Conformance is only three things: every non-reserved `.md` file has parseable frontmatter, every frontmatter block has a non-empty `type`, and reserved files follow their prescribed structure. Everything else in the specification is soft guidance.

Two rules shape Path more than the field list does:

**Producers may add custom keys, and consumers must preserve unknown keys.** This is what makes Path's extensions legal rather than a deviation.

**`index.md` and `log.md` are reserved filenames.** They cannot be concept documents. `index.md` is a directory listing with *no frontmatter at all*; `log.md` is a date-grouped history.

The practical consequence is worth stating plainly: **OKF gives Path almost nothing for free.** It defines no Task type, no status, no effort, no vocabulary of any kind — producers pick their own type values and consumers must tolerate whatever they find. What OKF contributes is the envelope and a guarantee that any OKF-aware consumer will read Path's files without choking on them. The schema below is Path's, not OKF's.

## Why Markdown and Not YAML

Tasks, requirements, blueprints, build log entries, the decisions log, and profile files are all `.md`. Given how much of their content is now structured data in frontmatter, `.yaml` is the obvious question. The answer is that **`.yaml` would put Path outside OKF entirely.**

A bundle is defined as a directory of Markdown files, and the first conformance requirement is that every non-reserved `.md` file has parseable frontmatter. A `.yaml` file is not a malformed OKF concept — it is not a concept at all. An OKF consumer scanning a bundle looks for `.md` and would never see it.

The reasoning behind OKF's design holds up on its own merits, independent of conformance. Frontmatter is metadata *about* a body, and the body is the point. OKF exists to hand agents curated prose with machine-readable headers attached to it. Strip the prose out and what remains is a database, which is precisely the thing OKF declines to be.

So the rule Path follows is: **Markdown files, with data pushed into frontmatter aggressively enough that a `yq` query answers every metric question without reading a body.** Prose that a human or an executor actually reads stays in the body.

| Document | Data (frontmatter) | Prose (body) |
|----------|--------------------|--------------|
| Task | status, effort, dates, change/drift/issue logs, traceability | Objective, Context, Scope, Acceptance Criteria, Validation, Notes |
| Decision Log | every row | why it tracks Decisions and not a full RAID log |
| Requirement | id, tags | the requirement text |
| Blueprint | tags | all of it — blueprints are reasoning |
| Build Log Entry | type label, date, related task | the honest account of what happened |
| Profile | tags | all of it |

**The cost of this choice, stated honestly:** with `.yaml` files, schema validation would come free from any JSON Schema tool. With OKF, Path writes its own validator. That is a real price of conformance, and it is a large part of why `path check` and the CLI are not optional extras.

## Type Vocabulary

OKF defines no type values, so Path defines its own. Consumers of a Path bundle must tolerate these; consumers of *other* bundles must expect not to recognise them.

| `type` | Applies to |
|--------|------------|
| `Task` | `tasks/T-NNN-*.md` |
| `Batch` | `tasks/B-NNN-*.md` |
| `Requirement` | `requirements/*.md` |
| `Blueprint` | `blueprints/*.md` |
| `Build Log Entry` | `build-log/*.md` |
| `Decision Log` | `decisions-log.md` |
| `Profile` | `$LCP_HOME/profile/*.md` |

## The `path:` Extension Namespace

Every Path-specific key lives under a single `path:` mapping rather than being scattered across top-level keys.

This is a deliberate choice with three reasons behind it. A single namespace cannot collide with fields a future OKF version might define. Every metric becomes one expression against a predictable location (`.path.status`, `.path.drift_log`). And any reader can see at a glance which keys are OKF's and which are ours. OKF's guarantee that consumers preserve unknown keys is what makes the namespace safe to rely on.

OKF v0.1 describes itself as a starting point rather than a finished standard. The `path:` namespace is the insurance policy against v0.2.

## Task Frontmatter

```yaml
---
type: Task
title: Sync with Path revisions
description: Bring the project's local Path copies back in line with the canonical repo.
tags: [path, maintenance]
timestamp: 2026-07-16T10:00:00Z
path:
  id: T-023
  status: pending            # pending | in-progress | complete | blocked
  effort: 3                  # Fibonacci: 1 | 2 | 3 | 5 | 8 | 13
  created: 2026-07-16
  updated: 2026-07-16
  completed:                 # null until status is complete
  project: lcm
  drafted_by: claude-opus-4-8
  completed_by: []
  requires: [T-019]          # prerequisite task ids
  implements: [F-13, NF-02]  # traceability to requirement ids
  change_log:
    - date: 2026-07-16
      status_at_change: pending
      note: Added acceptance criterion for link rewriting.
  drift_log:
    - date: 2026-07-16
      kind: correction       # correction | retry | post-completion-bug
      effort_to_correct: 2   # 1-3
      note: Approach corrected mid-build.
  issues:
    - date: 2026-07-16
      note: Found a broken link in the build log.
      resolution: Fixed in the same task.
  proof:                     # written by `path check`, never by hand
    checked_at:
    result:                  # pass | fail
---
```

The body keeps Objective, Context, Scope and Out of Scope, Tasks, Acceptance Criteria, Validation, and Notes.

### Provenance: Recorded, Estimated, or Inferred

Two optional keys mark a value that was *derived* rather than recorded:

| Key | Value | Meaning |
|-----|-------|---------|
| `effort_source` | `estimated` | Assigned retrospectively by a model, not recorded when the work was done |
| `completed_source` | `inferred-git` | Taken from the commit date the file entered the repository, not the date work finished |

**Absence of these keys means the value was recorded at the time**, which is the only kind of number that is really evidence. They exist because the projects migrated from work orders had no effort estimates at all and almost no completion dates, and those fields were backfilled — see [the decision](../build-log/2026-07-16-derived-metrics.md).

`path metrics` counts derived values into its `provenance` block, and the status page declares them above the charts. The risk being managed is not that an estimate is wrong; it is that a reader six months from now cannot tell an estimate from a measurement and treats both as fact. A task created by `path new task` carries neither key, because its numbers are real.

### Why the Logs Left the Body

The Change Log, Drift Log, and Issues Found sections used to be prose bullets in the body, parsed back out with regular expressions. They are now frontmatter lists, and **the prose sections no longer exist**.

Keeping both would guarantee they drift apart, and drift between two copies of the same fact is the exact failure Path exists to prevent. More importantly, the whole reason for the change is that `.path.drift_log` is now answerable without a parser — a body section would leave the parser in place and gain nothing.

This trade has a real cost. A YAML list is less pleasant to append to by hand than a Markdown bullet, and that cost lands on the human. It is why `path log drift|issue|change` exists: humans and agents append through the command rather than hand-editing YAML. Anyone editing frontmatter by hand is doing it the hard way.

## Batch Frontmatter

A batch groups tasks that are executed, and accounted for, together.

```yaml
---
type: Batch
title: Agent-facing CLI surface
description: ...
tags: [cli]
timestamp: 2026-09-04T10:00:00Z
path:
  id: B-002
  created: 2026-09-04
  updated: 2026-09-04
  project: path
  drafted_by: Human
  sequence: [T-114, T-116, T-117]   # intended execution order
---
```

The body keeps Goal, Why These Together, Sequence, and Notes.

### What a Batch Does Not Store

There is no `status` and no `completed`. Both are facts about the batch's members, computed on read: the status is `complete` when every member is, `in-progress` when any member is, `blocked` when a member is blocked and none is moving, and `pending` otherwise; the completion date is the last member to finish.

Storing either would put a second copy of something already recorded onto disk, where it would be correct only until the next time a member moved. This is the same reasoning that keeps a decision's age computed rather than stored (F-31), and `path check` fails a batch that carries either key.

### Membership and Order Live in Different Places

Membership is on the task, at `path.batch`. Order is on the batch, at `path.sequence`. That is one set of facts described by two files, which is exactly the shape Path usually refuses.

It is allowed here for two reasons. Every view that needs "which tasks are in this batch" is answering a question about tasks, and reading it off the tasks means never loading the batch file to answer it. And `path.sequence` is regenerated by `path batch add|remove|order` rather than authored, in the same way an index is regenerated rather than appended to.

What makes it safe rather than merely convenient is that `path check` fails a batch whose sequence does not name exactly the tasks claiming membership in it. The two cannot be committed apart, so the drift this normally invites has nowhere to happen.

## Decision Log Frontmatter

```yaml
---
type: Decision Log
title: lcm — Decisions Log
description: Open questions raised to the project owner that a task cannot proceed past.
tags: [decisions]
timestamp: 2026-07-16T10:00:00Z
path:
  decisions:
    - question: Should sync run before or after auth refresh?
      related_task: T-023    # null if none
      raised: 2026-07-16
      resolved:              # null while open
      answer:                # filled the moment it is resolved
---
```

The body keeps the preamble explaining why this file tracks Decisions and not a full RAID log. That is reasoning, and reasoning belongs in prose.

**The `Age (days)` column is gone.** It was a stored copy of a computed value: the file itself admitted the column was "for human skimming only" while the status page recomputed the real figure from `raised` and `resolved` every time it built. Two sources of truth for one number, one of them always going stale. Age is now computed at read time and never stored.

## Reserved Files

OKF forbids frontmatter on `index.md`. The rule for Path is therefore:

> Every non-reserved Path document carries OKF frontmatter. `index.md` and `log.md` follow OKF's reserved structure instead.

This means "OKF frontmatter on every file" cannot be stated as a flat rule anywhere in Path's requirements — the exemption is part of the specification, not an oversight.

`index.md` files exist for `.path/tasks/` and `.path/build-log/` to give an arriving agent progressive disclosure: a listing to scan before deciding what to read in full.

Path's `decisions-log.md` is *not* OKF's reserved `log.md`. The names are close enough to be worth saying out loud. It is an ordinary concept document with frontmatter.

## Metrics From Frontmatter

Every chart on the status page maps to a frontmatter query. No regular expressions, and no Python needed to *read* a metric.

Two details have to be right or the queries silently lie, so they are documented before the queries themselves.

### Which `yq`

**These examples require [mikefarah's `yq`](https://github.com/mikefarah/yq)** (`brew install yq`; verified against v4.53.3). Two unrelated tools are both called `yq`, and only this one works here. [Kislyuk's `yq`](https://github.com/kislyuk/yq) is a jq wrapper with no front matter support: it hands the whole file to a YAML parser and fails, for the reason below.

### Why `--front-matter=extract` is mandatory

`---` is YAML's *document separator*. A YAML parser handed an OKF file does not see frontmatter followed by prose — it sees one document, then another document made of Markdown. With a trivial body that accidentally parses; with a real one (a table, a colon inside a sentence, a fenced code block) it fails outright:

```
Error: bad file 'tasks/T-003.md': yaml: while scanning a block scalar at line 19 ...
```

The trap is that it fails *after* emitting some output, so a naive pipeline produces a plausible partial number instead of an error. `--front-matter=extract` outputs only the frontmatter and ignores the rest, which is exactly what is wanted.

### One file at a time

`--front-matter=extract` only applies to the first file in an argument list. Given a glob it errors on later files and leaks `---` separators into the output, so every query loops. This matches the pattern in yq's own documentation, which uses `find -exec` rather than a glob.

`grep .` drops the blank line yq prints for a file that yields no rows.

```bash
# Burn-up: completed effort points
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r '.path | select(.status == "complete") | .effort' "$f"
done | paste -sd+ - | bc

# Drift entries with effort to correct
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r '.path.drift_log[]? | [.date, .kind, .effort_to_correct] | @tsv' "$f"
done | grep .

# Every task by status
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r '.path | [.id, .status, .effort] | @tsv' "$f"
done | grep .

# Open decisions
yq --front-matter=extract -r \
  '.path.decisions[]? | select(.resolved == null) | [.raised, .question] | @tsv' \
  .path/decisions-log.md | grep .

# Points completed in the last 14 days — the rate the forecast rests on
since=$(date -v-14d +%F 2>/dev/null || date -d '14 days ago' +%F)
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r \
    ".path | select(.status == \"complete\") | select(.completed > \"$since\") | .effort" "$f"
done | grep . | paste -sd+ - | bc

# Points still to do — the numerator of the projection
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r '.path | select(.status != "complete") | .effort' "$f"
done | grep -v '^null$' | grep . | paste -sd+ - | bc

# Which tasks can be started: pending, with every prerequisite complete
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r \
    '.path | select(.status == "pending") | [.id, (.requires // [] | join(","))] | @tsv' "$f"
done | grep .

# Batch membership, read off the tasks rather than the batch
for f in .path/tasks/T-*.md; do
  yq --front-matter=extract -r '.path | select(.batch != null) | [.batch, .id, .status] | @tsv' "$f"
done | grep . | sort
```

The readiness query returns each pending task with its prerequisites rather than a
yes-or-no answer, because resolving them means looking up the status of other tasks
and `yq` reads one file at a time. That is a property of the tool, not of the data:
the fact is recorded, in a documented location, and the second lookup is the same
query run again. Batch membership needs no join at all — it is on the task, which is
[why it lives there](#membership-and-order-live-in-different-places).

`path metrics --json` assembles these into a single document, and the status page consumes that JSON rather than scraping Markdown.

This is what "a human or an AI can retrieve Path metrics directly from the OKF structures" ([F-32](../requirements/03-functional.md#metrics)) means in practice: the data is in the files, in a documented location, readable with a standard tool that Path did not write. The caveats above are the honest cost of that claim — the data is genuinely open, but the naive invocation is a trap, and pretending otherwise would just move the surprise to whoever tried it first.

## Linking

OKF supports bundle-absolute links (`/tasks/T-023-sync.md`) and relative links (`./T-023-sync.md`). A link from one concept to another asserts a relationship; the surrounding prose conveys what kind. Broken links are tolerated by the specification.

Path is stricter than OKF here: `path check` verifies that relative links resolve. A broken link in a Path bundle is a defect even though OKF would forgive it.

Structured relationships — `requires`, `implements` — live in frontmatter rather than being inferred from prose links, because they need to be queryable.
