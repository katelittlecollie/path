---
type: Build Log Entry
title: 2026-08-30 — Fixture Convention Added — A Fixture Must Build the World the Deploy Builds
description: ''
tags: [conventions, testing, deployment]
timestamp: 2026-08-30T00:00:00Z
path:
  date: 2026-08-30
  entry_type: CHANGE
  related_tasks: []
---

# 2026-08-30 — Fixture Convention Added — A Fixture Must Build the World the Deploy Builds

**Type:** CHANGE

## Summary

Added *A Fixture Must Build the World the Deploy Builds* to
[Document Conventions](../blueprints/03-conventions.md), directly after *A Check Must Be
Seen to Fail*: where a test's subject is deployment behaviour, its fixture must build the
environment the way the deploy builds it, and where it cannot, the shortcut must be named
rather than absorbed.

Three rules follow. Build from the real mechanism — migrations rather than a schema
autocreate, the platform's own connection-string shape rather than a hand-corrected one,
the roles and privileges the deploy grants rather than the container's defaults, nothing
seeded by an application helper the deploy never calls. Assert the fixture is not cheating,
by reading the privilege back rather than describing it in a comment. And keep it narrow,
because a second way to write every test is a way for the two to drift.

The review question it exists to prompt: *does this fixture build the world the way the
deploy builds it?*

## Why

Three production defects in one month on one project, all found in production or in a first
real CI run, none of them visible to a suite that was green throughout. The unifying
description: **a test that builds its world with the application's own convenience helpers
is testing the helpers, not the deployment.**

1. **A named driver.** Every Postgres test built its URL with `driver="psycopg"`. The
   managed platform hands out a bare `postgresql://`, which SQLAlchemy maps to a driver the
   project does not depend on. The application could not have started on that platform at
   all, and the suite was structurally incapable of noticing, because no test ever asked for
   the URL in the form the platform gives.
2. **A superuser rehearsal.** The stock database container's default user is a genuine
   superuser, and a superuser is exempt from every permission check including forced
   row-level security. The one rehearsal whose entire subject was "the database refuses
   cross-tenant access" ran against a role that could not be refused anything.
3. **A seeding helper.** Every entitlement and quota test built its plan catalog with the
   application's own seed function, which reads a constant and therefore always carries
   every key. Production builds the same catalog from the migration chain, which did not.
   Three days of refused billable writes, against a fully green suite.

The project's own notes after the second read *"Two now; worth watching for a third."* The
third arrived eight days later, which is what turned a count into a rule: this is not a
coincidence to keep tallying, it is a property of how the fixtures were written, and it
needed a fixture and a convention rather than another note.

## Relationship to the neighbouring convention

This is the sibling of *A Check Must Be Seen to Fail*, pointed at the harness instead of the
check. That rule asks whether the check can fail; this one asks whether the world it checks
is the world that ships. A guard can be perfectly falsifiable and still prove nothing,
because the environment it was falsified in is not the one production runs — which is
exactly what the superuser rehearsal was.

The two share a failure mode and a remedy. Both fail silently, by reporting the success
everyone wanted; both are closed by making the harness state a property out loud and then
asserting it.

## Scope note

Deliberately not "every test must go through migrations". Most tests are about logic, where
the fast fixtures are correct and their speed is worth having, and a suite that pays
migration cost everywhere buys no additional signal for it. The line is subject matter: a
test whose answer depends on **how the environment was built** belongs on the slow fixture;
a test whose answer depends on what the code computes does not.

The wording deliberately generalises past databases, because the same shape is available
anywhere a test constructs an environment — a config dict assembled in the test rather than
loaded the way the application loads it, or a credential present in a test run only because
the developer happens to have one on disk.
