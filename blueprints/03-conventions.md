---
type: Blueprint
title: Document Conventions
description: The conventions every Little Collie Path document follows.
tags: [conventions, frontmatter, logging, verification]
timestamp: 2026-07-16T00:00:00Z
---

# Little Collie Path — Document Conventions

## Frontmatter

Every Path document is an OKF concept: YAML frontmatter with a non-empty `type`, followed by a Markdown body. The reserved filenames `index.md` and `log.md` are the only exceptions — OKF forbids frontmatter on them.

All Path-specific fields live under a single `path:` mapping. The full schema, the type vocabulary, and the reasoning behind both are in [OKF Mapping](./06-okf-mapping.md). This document covers when to write what; that one covers where it goes.

**Structured data goes in frontmatter; prose goes in the body.** The dividing line is whether something is read or queried. If a metric depends on it, it is frontmatter.

## Requirement Identifiers

Functional requirements are prefixed `F-` followed by a two-digit number (e.g., `F-01`). Non-functional requirements are prefixed `NF-`. These identifiers are stable — once assigned, they do not change even if the requirement is updated. A deprecated requirement is marked `[DEPRECATED]` rather than renumbered.

Tasks reference requirements by identifier in `path.implements`, so the traceability is queryable rather than buried in prose.

## Task Identifiers

Tasks are `T-NNN`, zero-padded to three digits, allocated by `path new task`. Numbers are sequential, and `path.id` must match the filename.

A number that any document refers to is never reused — `path new task` searches the tasks, the build log, the requirements, the blueprints, the decisions log, and `AGENTS.md` before allocating, not just the tasks directory. Deleting a task therefore does not free its number. If it did, the build log's history would end up describing two different pieces of work under one id, and the log is the thing that has to stay trustworthy. The one exception is a task deleted before anything ever mentioned it: that number is free, and reusing it is harmless precisely because no history points at it.

Tasks were called work orders (`WO-NNN`) before Path adopted OKF. Build log entries written before the migration still say "work order"; that language is left alone, because rewriting the prose of a historical record to match present terminology would be a lie about what happened.

## Batch Identifiers

Batches are `B-NNN`, zero-padded to three digits, allocated by `path new batch`, and they live in `tasks/` alongside the tasks they group. They share the task rule that a number any document refers to is never reused, and for the same reason: the build log has to keep meaning one thing.

A batch document records the intended execution order at `path.sequence`. Membership is recorded on each task at `path.batch`, and a task belongs to at most one batch. Both are written by `path batch add|remove|order`; `path check` fails a batch whose sequence does not name exactly the tasks claiming it, so the two halves cannot be committed apart. See [OKF Mapping](./06-okf-mapping.md#batch-frontmatter).

**A batch has no stored status and no stored completion date.** Both are computed from its members on read — `complete` when every member is, `in-progress` when any member is, `blocked` when a member is blocked and none is moving, `pending` otherwise. Writing either to disk would be a second copy of something already recorded, correct only until the next time a member moved. `path check` rejects a batch that carries either key.

### When to Batch, and When Not To

A batch exists to make the bookkeeping proportional to the work. Completing a task requires a retrospective naming it, a validation run, an `AGENTS.md` update, and a pass through the Definition of Done. On a one- or two-point task that ceremony is most of the cost, and paying it four times for four small tasks buys nothing the first payment did not already buy. `path batch start|complete` moves the members together, `path check B-NNN` validates them together, and one `RETROSPECTIVE` naming all of them in `path.related_tasks` closes all of them.

What a batch does not do is lower the standard. Every rule still applies to every member; it just applies once. `path batch complete` refuses a batch containing a task that was never started, because completing work that was never in progress would leave the burn-up with no interval to measure — the same refusal the task-level transition table makes, for the same reason.

The test for whether something is a batch is whether it has an outcome its members do not have separately. Tasks that merely happen to be adjacent in the backlog are a list, and a list does not need a document. Tasks that share a surface, a body of context, or a correction that has to land with the code it corrects are a batch. If a member could ship a month later without anything becoming false, it is in the wrong batch.

Batches are optional and belonging to none is the ordinary case. A task that is genuinely self-contained — which F-14 and F-15 say every task should be — loses nothing by standing alone.

## Status Fields

### Task Status

Recorded at `path.status`:

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `in-progress` | Actively being worked |
| `complete` | All acceptance criteria met |
| `blocked` | Cannot proceed; blocking issue documented in the task |

A batch carries the same four values, derived from its members rather than recorded. Do not write a status into a batch document.

Transitions are enforced by `path task start|block|complete`. `path.completed` is set if and only if the status is `complete`, and the tooling maintains that — not the author.

### Build Log Entry Types

Build log entries carry their type label in frontmatter and open with it in the body, to aid scanning:

| Label | When to use |
|-------|-------------|
| `DECISION` | An architectural or design decision was made |
| `PROBLEM` | A problem was encountered (may or may not be resolved) |
| `RESOLUTION` | A previously logged problem was resolved |
| `CHANGE` | A requirement or blueprint was updated |
| `RETROSPECTIVE` | End-of-task reflection |
| `SESSION-CLOSE` | End-of-session summary for human continuity |

### Strategy Notes

Strategy notes live in `strategy/`, carry `type: Strategy Note` in frontmatter,
and hold speculation, debate, and direction-setting — the thinking that happens
*before* anything is settled. This is the one place where an entry is allowed to
argue several ways and reach no conclusion.

The line against the build log is the tense. A build-log entry reports what has
already happened: a decision made, a problem hit, a blueprint changed. A
strategy note reasons about what *might* happen: options, trade-offs, a
direction worth trying. Keep exploration out of the build log and settled facts
out of `strategy/`. When a strategy thread resolves, record the outcome where
settled things live — a `DECISION` build-log entry, `decisions-log.md`, or an
updated requirement or blueprint — and let the strategy note stand as the record
of how the thinking got there. Strategy notes are informal by design and carry
no type label beyond `Strategy Note`; they are validated only for OKF
conformance, not for any lifecycle.

## Effort Estimate Scale

Every task carries an effort estimate at `path.effort`, assigned before it is ready to start (see the Definition of Ready). Points follow the Fibonacci sequence and reflect relative complexity and scope — not time. A task executed by a human and the same task executed by an AI agent get the same point value; how long either takes to finish it is a separate question the estimate doesn't answer.

| Points | Meaning |
|--------|---------|
| `1` | Trivial; a single, narrow, unambiguous change |
| `2` | Small; one file, well-understood, no design judgment |
| `3` | One or two files, minor judgment calls |
| `5` | A few files, some design judgment required |
| `8` | Several files or areas, real design judgment |
| `13` | Many files or areas, or open design questions |
| `21` | Spans the system; open design questions and unknowns that only surface during the work |
| `34`+ | Larger still. Consider whether it is really one task. |

**There is no maximum.** The sequence continues — 34, 55, 89 — and the tooling accepts any Fibonacci number. This matters more than it looks: a ceiling silently compresses everything above it into one bucket, so the hardest piece of work in a project becomes indistinguishable from a merely large one, and the burn-up under-reports precisely where the risk was. If a task needs 34, give it 34.

A number above 21 is also worth reading as a signal rather than just a size. Work that large usually has a seam in it, and a task that can be split is easier to estimate, easier to review, and easier to finish. Splitting is a judgment call, not a rule — but the question should be asked.

### What the Estimate Measures

The estimate is of the work as understood when it is assigned: scope, breadth, and how much is genuinely unknown. It is not a prediction of how painful the task will turn out to be, and the two diverge. A task whose scope reads modestly can still be the hardest thing in the project, because the difficulty was hiding somewhere nobody looked.

That divergence is not a flaw in the estimate — it is information. When a task turns out far harder than its points suggested, the gap belongs in the drift log and in a `RETROSPECTIVE`, where it can teach the next estimate something. Do not quietly revise history to match the outcome; a scale corrected after the fact measures nothing at all.

## Logging

The three task logs — issues, change, drift — are frontmatter lists, not body sections. Append to them with `path log`, which stamps the date and, where relevant, the task's status at the moment of the entry:

```bash
path log issue T-023 "Found a broken link in the build log" --resolution "Fixed in the same task"
path log change T-023 "Added an acceptance criterion for link rewriting"
path log drift T-023 --kind correction --effort 2 "Approach corrected mid-build"
```

Hand-editing the YAML is possible and unpleasant. Use the command.

### Logging Human-Found Issues

When a human finds a bug or issue while a task is in progress — whether or not it's related to that task's scope — log it to `path.issues` immediately, not at session close. Include what was found, how, and its resolution or current status.

These entries are the input to the process-improvement review that `path close` performs: at session close, Path reviews all logged issues and checks whether a gap in the requirements, blueprints, or the task itself let the issue through, recommending documentation or process changes if so. Logging issues against the task — rather than only in memory, or in a build log entry after the fact — is what makes that review possible.

### Logging Requirements Volatility

Any time a task's Scope, Tasks, or Acceptance Criteria change after it was first created — by the AI or a human — log it to `path.change_log`. Each entry records `status_at_change`, the task's status at the moment of the change. Impact is classified from that status, not from a separate judgment call:

| Status at time of change | Impact |
|--------------------------|--------|
| `pending` | Low — nothing has started yet |
| `in-progress` | Medium — work is underway |
| `complete` | High — the task was already considered done |

`path log change` captures the status automatically, which is the point: the classification cannot be fudged after the fact.

### Logging AI Workflow Drift

Path exists to keep AI builds inside a scoped, well-understood boundary. Drift is when execution moves outside that boundary and has to be pulled back. Log it to `path.drift_log` as it happens.

- **A human correcting the AI's approach mid-build** counts as drift. A human simply adding information they forgot the first time does not — "Sorry, I forgot to say...", "Also, can you also handle..." is new scope, not a correction to a wrong approach. The distinction is whether the AI was doing the wrong thing, or was correctly doing what it knew given incomplete instructions.
- **A smaller model requiring a retry in multi-agent execution** counts as drift, regardless of cause.
- **A bug found after the task was marked `complete`** counts as drift. Log it with `--kind post-completion-bug`; if it was found during a later task's execution, also log it to that later task's `path.issues` per the convention above.

Each entry carries an `effort_to_correct` on a 1–3 scale (1 = trivial re-ask, 2 = some rework, 3 = significant rework) — deliberately coarser than the effort estimate scale, since a correction is a fraction of a task, not a unit of work in its own right.

### Logging Decisions

When the Definition of Ready's Ambiguity Check surfaces a question that has to go to the project owner before work can proceed, record it with `path decision raise` the moment it's raised, and `path decision resolve` the moment it's answered. Rows live in `decisions-log.md`'s frontmatter; see that file's body for why it covers only Decisions and not a full RAID log.

A decision's age is computed from `raised` and `resolved` when something asks for it. It is never stored — a stored age is a fact that starts going stale the moment it is written.

## Metrics and the Status Page

Every metric is a frontmatter query. `path metrics --json` assembles them; anyone can also ask directly with `yq`, which is the point of the schema. See [OKF Mapping](./06-okf-mapping.md#metrics-from-frontmatter).

Every project has a `status.html` built from that metrics document. It charts:

- **Burn-up** — total backlog vs. completed vs. remaining effort points, plotted against each task's `completed` date.
- **Requirements volatility** — change log entries over time, by impact.
- **Decision edge latency** — open and recently resolved decisions, sorted by computed age.
- **AI workflow drift** — drift log entries (plus post-completion issues) over time, sized by effort to correct.

`path close` regenerates it after writing the session-close build log entry. It is never hand-edited.

## Linking Between Documents

Use relative Markdown links to reference other documents:

```markdown
See [system architecture](../blueprints/01-architecture.md).
This implements [F-13](../requirements/03-functional.md#tasks).
```

Tasks must link to the specific requirements and blueprint sections they implement or depend on, so that a task can be traced back to its requirements and forward to the build log entry documenting its completion. Structured relationships (`path.requires`, `path.implements`) live in frontmatter because they must be queryable; prose links carry the explanation.

OKF tolerates broken links. Path does not: `path check` verifies that relative links resolve.

## Writing Style

**Requirements** should be written in imperative form: "The system must...", "Each project must contain...". Avoid "should" for requirements — if it's a requirement, it must be met; if it's a preference, note it as guidance rather than a requirement.

**Blueprints** should be written descriptively, explaining both the decision and the reasoning. "We use X because Y" is more valuable than "We use X."

**Tasks** should be written as instructions to an executor who is competent but has no prior context on this project. Assume they can read and follow instructions; don't assume they know what you were thinking.

**Build log entries** should be written honestly and specifically. "This was hard because..." is useful. Vague summaries are not.

## Document Freshness

A document that is known to be inaccurate is worse than no document. When something changes:

1. Update the relevant requirements or blueprint file directly.
2. Write a build log entry of type `CHANGE` explaining what changed and why.
3. Update any tasks that reference the changed content, if they are still pending.

Do not append correction notes to the end of documents. Update the source of truth and log the change.

## Reporting a Check That Did Not Run

A check that was skipped, disabled, or could not reach what it needed **must name the condition that caused it, specifically enough to be falsified.** "Needs a reachable inference host" is an assertion about the world. "Could not reach `http://localhost:11434`" is a fact about an attempt — and only the second invites the obvious question, which is whether that was the right address.

The failure this prevents is not a check that breaks. It is a check that quietly stops running and then reads, at a glance, like a considered conclusion. A failing test demands attention; a skipped one is a single character in a row of dots, and its message is the only thing standing between "we verified this" and "we did not".

The worked example this rule came out of: a test that ran a classifier five times against a local model and asserted it answered consistently. On one machine it skipped, with the message `needs a reachable Ollama`. Read as a fact about the machine, that justified holding a task blocked and deferring the measurement to a future session. It was not a fact about the machine. The test had asked a benchmark helper that hardcodes `localhost` instead of the project's own configuration file, which named a host on the LAN that was up throughout. The measurement took 67 seconds. Had the message named the address it tried, the mistake would have been visible in the skip line itself.

Two rules follow. They apply to any verification a project runs — a test, a lint or accessibility gate, a CI job, a manual check recorded in a task:

1. **The skip names the condition.** Print the endpoint, the missing binary, the unset variable, the absent fixture, the credential that was not found. A condition that cannot be printed is usually a condition that was not really checked.
2. **A blocker names the measurement that established it.** Writing "the tool is not installed" in a task or a session-close entry is a claim, and it should be the claim that was actually tested. If what matters is whether an endpoint answers, `which` is the wrong command and its output is not evidence. A blocker asserted from the wrong measurement is worse than an unexamined one, because it looks settled.

This is Document Freshness applied to the record a check leaves behind: a document known to be inaccurate is worse than no document, and a skip message is a document. It is also the cheapest member of a broader family — a guard whose failure mode is a pass — and it is the cheap one precisely because a skip already has a message field whose entire job is to say why.

## A Check Must Be Seen to Fail

**A check a task adds or repairs must be observed failing, for the reason it exists to
catch, before the task is complete.** Until it has failed once, a passing check is not
evidence — it is equally consistent with the thing working, the check testing something
else, and the check not running at all.

This covers two shapes, and they are the same rule pointed at different objects:

- **A guard** — a test assertion, a lint or accessibility gate, a CI job, a validator, a
  script that exits non-zero on a condition. It owes a **negative control**: something
  that makes it fail on purpose, run once, confirming it can.
- **A test pinning a diagnosed defect** — a regression test. It owes a run against the
  **unmodified code**, confirming it fails there.

### Why a passing check is not evidence

The failure mode is a guard whose failure mode is a pass, and it is quiet by
construction. A broken check does not announce itself the way broken code does: it
reports success, which is what everyone wanted to hear, and the louder the suite the
better it hides. Five defects of this exact shape are on record across projects using
Path, and in every one the guardrail existed, was pointed at the right thing on paper, and
was itself unfalsifiable:

- An accessibility and HTML gate whose login step never logged in — so it audited the
  login page nineteen times per theme and reported clean.
- A launcher failure masked behind that same gate.
- An HTML validator that exited 0 without a JRE ever starting.
- A test asserting "an un-bannable card carries no ban hook", which passed against the
  page's shortcut script rather than the card markup, because its helper sliced to
  end-of-document.
- A regression test for a database lock error that passed against completely unhardened
  code, because the driver's default already absorbed the case it reproduced.

None of these were caught by review, by lint, or by the suite going green. Each was caught
— eventually, and late — by someone asking the question this rule asks up front.

### The defect-test half, in detail

The distinction that matters is between a test that *covers* a defect and a test that
*could have caught* it. Writing the fix first and the test second is normal and fine; what
is not fine is never checking which of the two you wrote. A test authored against
already-fixed code passes on the first run, and a first-run pass carries no information at
all.

What this prevents specifically is a **misdiagnosis that ships green**. The sequence is
ordinary: a defect report names a cause, the cause sounds right, the fix follows from it,
the test follows from the fix, everything passes, the task closes. Nothing in that chain
ever asks whether the named cause was the real one.

The worked example: an incident report attributed a database lock error to a missing
timeout setting. Both halves were wrong — the driver already set one by default, and the
conflict that actually occurred was one where the timeout is bypassed entirely. The
plausible fix (raise the timeout) would have passed a test written against it, closed the
task, and left the defect in place. What caught it was running the reproduction against the
*unfixed* code to confirm it failed there. It did not. Sixty seconds, and the diagnosis in
the incident report turned out to be a hypothesis wearing a finding's clothes.

### The rules

1. **Make it fail, on purpose, once.** For a defect test, run it against the unmodified
   code — revert the fix, stash it, or point the test at an unhardened equivalent. For a
   guard, feed it the thing it is supposed to reject. Some form of this is nearly always
   cheap.
2. **Check the failure *reason*, not just the failure.** A check that fails for an
   unrelated reason — a missing fixture, a different error, a crash on startup — has told
   you nothing either. The failure must be the one the check exists to produce.
3. **Where the negative case can be kept, keep it.** A permanent test asserting the raw
   failure against an unmodified equivalent stops the fix from being deleted while the
   positive check goes on passing for some other reason. This is the difference between
   proving it *could* fail once and keeping it falsifiable.
4. **Where it genuinely cannot be done, say so in the build log** — naming what was tried,
   in the terms *Reporting a Check That Did Not Run* requires. An unverifiable check is not
   forbidden; an unverifiable check nobody flagged is.

### Scope

This applies to a check a **task adds or repairs**, and to tests pinning a **diagnosed**
defect. It is deliberately *not* "prove every negative assertion can fail" — a rule that
reads `x not in y` must always ship a control is correct in principle and unaffordable in
practice, and a rule nobody can follow is a rule that gets skipped everywhere including
where it mattered.

The line is ownership and intent, not test type. If a task's point is that something is now
caught, that catching is the deliverable and it needs the same proof as any other
deliverable. An assertion written in passing, as part of ordinary coverage, does not.

This is the same family as *Reporting a Check That Did Not Run* above, one rung up in cost.
A skip message is the cheap corner — a skip already has a field whose job is to say why, so
filling it in is not a new mechanism. This one costs a deliberate extra run, and buys the
thing that run is uniquely able to tell you: whether the check checks.

## A Fixture Must Build the World the Deploy Builds

**A test that constructs its world with the application's own convenience helpers is
testing the helpers, not the deployment.** Where a test's subject is deployment behaviour,
its fixture must build the environment the way the deploy builds it — and where it cannot,
the shortcut must be named rather than absorbed.

The shape is a shortcut past something a deploy actually does. Each one is invisible in a
green suite, because the fixture and the assertion agree with each other; what they do not
agree with is production.

### The evidence

Three defects in one month on one project, all found in production or in a first real CI
run, none catchable by the suite that was passing at the time:

- **A named driver.** Every Postgres test built its URL with `driver="psycopg"`. The
  managed platform hands out a bare `postgresql://`, which SQLAlchemy maps to a driver the
  project did not depend on. The application could not have started there at all, and no
  test could see it, because no test ever asked for the URL in the form the platform gives.
- **A superuser rehearsal.** The stock database container's default user is a genuine
  superuser, and a superuser is exempt from the forced row-level-security the whole
  isolation story rests on. The rehearsal seeded happily with no tenant context and proved
  nothing about the policy it was there to prove.
- **A seeding helper.** Every entitlement and quota test built its catalog with the
  application's `seed_default_plans`, which reads a constant and therefore always carries
  every key. Production builds the same catalog from the migration chain, which did not.
  Three days of refused billable writes against a fully green suite.

A fourth is arguably already present wherever a credential exists in a test only because
the developer running it happens to have one on disk.

### The rule

For a test whose subject is **deployment behaviour** — how the environment is built, not
what the code computes with it:

- Build from the real mechanism. Migrations to head, not `create_all`. The platform's own
  connection-string shape, not a hand-corrected one. The roles and privileges the deploy
  grants, not the container's defaults. Nothing seeded by an application helper the deploy
  never calls.
- Assert the fixture is not cheating. A comment saying the role is unprivileged is not
  evidence; read the attribute back and assert it. This is *A Check Must Be Seen to Fail*
  applied to the harness rather than to the check.
- Keep it narrow. Most tests are about logic, where the fast fixtures are the right tool
  and their speed is worth having. Forcing a whole suite through migrations trades real
  runtime for no extra signal, and a second way to write every test is a way for the two to
  drift. Name which suites use which, and why.

### The review question

*Does this fixture build the world the way the deploy builds it?*

Ask it wherever a test constructs an environment — not only a database. A config dict
assembled in the test rather than loaded the way the application loads it, a credential
present because the developer has one, a client stubbed at a layer the deploy does not
have: same shape, same silence.

## Session-Close Convention

At the end of every working session, write a `SESSION-CLOSE` build log entry with `path close`. This is the primary tool for human continuity — it gives a clear re-entry point when returning to a project after any gap.

A session-close entry must include:

- **Completed this session** — what was finished or meaningfully progressed
- **Current task** — what is actively in flight (auto-populated)
- **State at close** — what is working, what is mid-flight
- **Next session — start here** — the specific first action for the next session; concrete enough that re-reading everything won't be necessary
- **Blockers / open questions** — anything unresolved (omit the section if none)

Session-close entries are for the human, not for the AI. An agent should re-derive state from the tasks and blueprints at the start of each session. The session-close entry is the fast path for a human who needs to reorient quickly.

## AGENTS.md Maintenance

`AGENTS.md` is a navigation guide, not a record. Every AI agent reads the whole file at the start of every session — anything that makes it longer makes every future session more expensive to start, forever. Two fields are the common failure point, and each is a hard one-line limit:

**Current Task** — exactly one line: the task id, its status, and enough of the title to recognize it (e.g. `T-023 (pending) — Sync with Path revisions; see .path/tasks/T-023-sync-with-path-revisions.md`). Never inline what the task contains, what it fixed, what a human did to unblock it, or any other narrative — that content belongs in the task itself, which is exactly what it's for, or in a build log entry. Update this field whenever:

- A new task is started (set it to the new task)
- A task is completed (clear it, or set it to the next pending task)
- A task is blocked (note the block, still one line)

**Project Status** — the `**Phase:**` line stays one line naming the current phase (e.g. `T-022 complete, T-018 pending`), and `**Last updated:**` stays one line. Do not append a `**Phase (prior):**` block, or any block, every time a task completes — that turns Project Status into an ever-growing changelog. The changelog already exists: it's the build log. If a fact about *why* the project is in its current state matters, it belongs in a `RETROSPECTIVE` or `CHANGE` build log entry, not folded into `AGENTS.md`.

`path check` enforces both limits mechanically, so this is no longer a rule an agent has to remember.

## Precedence

A project's own documentation overrides the global profile on any conflict. A project that contradicts a global rule must do so deliberately and in writing, in its blueprints. See [Profile and Precedence](./07-profile-and-precedence.md).
