---
type: Decision Log
title: path — Decisions Log
description: Open questions raised to the project owner that a task cannot proceed past.
tags: [decisions]
timestamp: 2026-07-17T00:43:22Z
path:
  decisions: []
---

# Decisions Log

Tracks open questions raised to the project owner that a task can't proceed past without an answer — the moment the Definition of Ready's Ambiguity Check says "raise it as a question before proceeding," it gets a row here.

This deliberately covers only Decisions, not a full RAID log. Risks already live in a task's `blocked` status, Assumptions belong inline in the relevant blueprint, Issues live in each task's Issues Found section, and Dependencies live in each task's Prerequisites section — duplicating those here would just create a second place to keep in sync.

Log a row the moment a question is surfaced. Update **Resolved** the moment it's answered — don't backfill from memory. The **Age (days)** column is for human skimming only; `path-status-page` always computes the real figure from **Raised** and **Resolved** (or today, if still open) when it builds the status page.
