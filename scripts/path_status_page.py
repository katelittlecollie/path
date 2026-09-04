#!/usr/bin/env python3
"""Render status.html from `path metrics`.

Implements F-34. This script used to parse work order bodies with regular
expressions to find effort estimates, change logs, drift logs, and issues. It
no longer parses anything: every figure arrives as JSON from scripts/metrics.py,
which reads frontmatter. The charts are unchanged; only where the numbers come
from has changed.

The page is fully regenerated on every `path close` and is never hand-edited.
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import metrics  # noqa: E402
import okf  # noqa: E402


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__PROJECT__ — Path Status</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff; --fg: #1a1a1a; --muted: #666; --border: #ddd;
    --low: #6aa84f; --medium: #e69138; --high: #cc4125;
    --line1: #3d7fd9; --line2: #999;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #16181d; --fg: #e8e8e8; --muted: #999; --border: #333; }
  }
  * { box-sizing: border-box; }
  body { background: var(--bg); color: var(--fg); font: 14px/1.5 -apple-system, system-ui, sans-serif; margin: 0; padding: 2rem; }
  h1 { font-size: 1.3rem; margin: 0 0 .25rem; }
  .meta { color: var(--muted); font-size: .85rem; margin-bottom: 2rem; }
  section { margin-bottom: 2.5rem; }
  h2 { font-size: 1rem; border-bottom: 1px solid var(--border); padding-bottom: .4rem; }
  .empty { color: var(--muted); font-style: italic; }
  svg { max-width: 100%; height: auto; overflow: visible; }
  .axis { stroke: var(--border); stroke-width: 1; }
  .axis-label { fill: var(--muted); font-size: 11px; }
  table { border-collapse: collapse; width: 100%; font-size: .85rem; }
  th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
  tr.open td.age { color: var(--high); font-weight: 600; }
  .legend { display: flex; gap: 1rem; font-size: .8rem; color: var(--muted); margin-top: .5rem; }
  .derived-note { border-left: 3px solid var(--medium); background: color-mix(in srgb, var(--medium) 8%, transparent); padding: .6rem .8rem; margin: -1rem 0 2rem; font-size: .85rem; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
  .forecast { display: flex; flex-wrap: wrap; gap: 2rem; border: 1px solid var(--border); border-radius: 4px; padding: 1rem 1.2rem; margin-bottom: 2rem; }
  .forecast .figure { font-size: 1.4rem; font-weight: 600; }
  .forecast .label { color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }
  .forecast .caveat { flex-basis: 100%; color: var(--muted); font-size: .85rem; }
  .board-group { margin-bottom: 1.4rem; }
  .board-group h3 { font-size: .9rem; margin: 0 0 .5rem; }
  .board-group h3 .progress { color: var(--muted); font-weight: 400; }
  .row { display: flex; gap: .8rem; align-items: baseline; padding: .3rem 0 .3rem .8rem; border-left: 3px solid var(--line1); }
  .row.secondary { border-left-color: var(--border); color: var(--muted); }
  .row .id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem; }
  .row .note { font-size: .8rem; color: var(--muted); margin-left: auto; }
</style>
</head>
<body>
<h1>__PROJECT__ — Path Status</h1>
<div class="meta">Generated __GENERATED__ by <code>path close</code></div>__PROVENANCE__
__FORECAST__
<section id="board-section">
  <h2>Backlog</h2>
__BOARD__
</section>

<section id="burnup-section">
  <h2>Burn-up</h2>
  <div id="burnup"></div>
  <div class="legend">
    <span><span class="swatch" style="background:var(--line1)"></span>Completed (cumulative)</span>
    <span><span class="swatch" style="background:var(--line2)"></span>Remaining</span>
  </div>
</section>

<section id="volatility-section">
  <h2>Requirements Volatility</h2>
  <div id="volatility"></div>
  <div class="legend">
    <span><span class="swatch" style="background:var(--low)"></span>Low (pending)</span>
    <span><span class="swatch" style="background:var(--medium)"></span>Medium (in-progress)</span>
    <span><span class="swatch" style="background:var(--high)"></span>High (complete)</span>
  </div>
</section>

<section id="decisions-section">
  <h2>Decision Edge Latency</h2>
  <div id="decisions"></div>
</section>

<section id="drift-section">
  <h2>AI Workflow Drift</h2>
  <div id="drift"></div>
  <div class="legend">
    <span><span class="swatch" style="background:var(--low)"></span>Correction</span>
    <span><span class="swatch" style="background:var(--medium)"></span>Retry</span>
    <span><span class="swatch" style="background:var(--high)"></span>Post-completion bug</span>
  </div>
</section>

<script>
const DATA = __DATA__;
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function svg(w, h) { return el("svg", {viewBox: `0 0 ${w} ${h}`, width: "100%"}); }
function empty(container, msg) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = msg;
  container.appendChild(p);
}

// Dates are ten characters wide and ticks are not, so a horizontal axis label
// collides with its neighbours as soon as there are more than a handful of
// them — and a burn-up gets one tick per completed task, so that is always.
// Rotating -45 with the anchor at the end hangs each label down-left from its
// own tick: they stop overlapping, and the tick a label belongs to is the one
// its text points at. Reading them is a head-tilt to the left.
function dateLabel(x, y, text) {
  const t = el("text", {class: "axis-label", x: x, y: y, "text-anchor": "end",
                        transform: `rotate(-45, ${x}, ${y})`});
  t.textContent = text;
  return t;
}

// ── Burn-up: two lines (completed cumulative, remaining) over dates ────────
(function () {
  const container = document.getElementById("burnup");
  const pts = DATA.burnup.points;
  const total = DATA.burnup.backlog_total;
  if (!total) { empty(container, "No tasks with an effort estimate yet."); return; }
  // PADB is deeper than PAD because the date labels below the axis are rotated
  // and a rotated ten-character label is about 55px tall.
  const W = 800, H = 300, PAD = 40, PADB = 95;
  const s = svg(W, H);
  const n = pts.length;
  const x = i => PAD + (n === 1 ? 0 : (i / (n - 1)) * (W - 2 * PAD));
  const y = v => H - PADB - (v / total) * (H - PAD - PADB);
  s.appendChild(el("line", {class: "axis", x1: PAD, y1: H - PADB, x2: W - PAD, y2: H - PADB}));
  s.appendChild(el("line", {class: "axis", x1: PAD, y1: PAD, x2: PAD, y2: H - PADB}));
  const mkPath = (key) => pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p[key])}`).join(" ");
  s.appendChild(el("path", {d: mkPath("completed"), fill: "none", stroke: "var(--line1)", "stroke-width": 2}));
  s.appendChild(el("path", {d: mkPath("remaining"), fill: "none", stroke: "var(--line2)", "stroke-width": 2, "stroke-dasharray": "4,3"}));
  pts.forEach((p, i) => {
    s.appendChild(el("circle", {cx: x(i), cy: y(p.completed), r: 3, fill: "var(--line1)"}));
    s.appendChild(dateLabel(x(i), H - PADB + 14, p.date));
  });
  const totalLabel = el("text", {class: "axis-label", x: PAD, y: PAD - 8});
  totalLabel.textContent = `Backlog total: ${total} points`;
  s.appendChild(totalLabel);
  container.appendChild(s);
})();

// ── Requirements volatility: stacked bars per week, colored by impact ───────
(function () {
  const container = document.getElementById("volatility");
  const buckets = DATA.volatility;
  if (!buckets.length) { empty(container, "No work order changes logged yet."); return; }
  const W = 800, H = 300, PAD = 40, PADB = 95;
  const max = Math.max(...buckets.map(b => b.low + b.medium + b.high), 1);
  const s = svg(W, H);
  const bw = (W - 2 * PAD) / buckets.length;
  s.appendChild(el("line", {class: "axis", x1: PAD, y1: H - PADB, x2: W - PAD, y2: H - PADB}));
  buckets.forEach((b, i) => {
    const bx = PAD + i * bw + bw * 0.15;
    const barW = bw * 0.7;
    let yTop = H - PADB;
    [["low", "var(--low)"], ["medium", "var(--medium)"], ["high", "var(--high)"]].forEach(([k, color]) => {
      const h = (b[k] / max) * (H - PAD - PADB);
      yTop -= h;
      s.appendChild(el("rect", {x: bx, y: yTop, width: barW, height: h, fill: color}));
    });
    s.appendChild(dateLabel(bx + barW / 2, H - PADB + 14, b.period));
  });
  container.appendChild(s);
})();

// ── Decision edge latency: table sorted open-first, oldest-first ───────────
(function () {
  const container = document.getElementById("decisions");
  const rows = DATA.decisions;
  if (!rows.length) { empty(container, "No decisions logged yet. Raise one with `path decision raise`."); return; }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Decision</th><th>Task</th><th>Raised</th><th>Resolved</th><th>Age (days)</th></tr></thead>";
  const tbody = document.createElement("tbody");
  rows.forEach(d => {
    const tr = document.createElement("tr");
    if (d.open) tr.className = "open";
    tr.innerHTML = `<td>${d.question}</td><td>${d.task || "—"}</td><td>${d.raised}</td><td>${d.resolved || "open"}</td><td class="age">${d.age_days}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
})();

// ── AI workflow drift: bar per event, height = effort, colored by type ──────
(function () {
  const container = document.getElementById("drift");
  const events = DATA.drift;
  if (!events.length) { empty(container, "No drift logged yet."); return; }
  const W = 800, H = 300, PAD = 40, PADB = 95;
  const colorOf = { correction: "var(--low)", retry: "var(--medium)", "post-completion-bug": "var(--high)" };
  const max = Math.max(...events.map(e => e.effort), 3);
  const s = svg(W, H);
  const bw = (W - 2 * PAD) / events.length;
  s.appendChild(el("line", {class: "axis", x1: PAD, y1: H - PADB, x2: W - PAD, y2: H - PADB}));
  events.forEach((e, i) => {
    const bx = PAD + i * bw + bw * 0.15;
    const barW = bw * 0.7;
    const h = (e.effort / max) * (H - PAD - PADB);
    const rect = el("rect", {x: bx, y: H - PADB - h, width: barW, height: h, fill: colorOf[e.type] || "var(--muted)"});
    const title = el("title", {});
    title.textContent = `${e.date} — ${e.task} — ${e.type} (effort ${e.effort})\\n${e.description}`;
    rect.appendChild(title);
    s.appendChild(rect);
    s.appendChild(dateLabel(bx + barW / 2, H - PADB + 14, e.date));
  });
  container.appendChild(s);
})();
</script>
</body>
</html>
"""


def forecast_banner(data: dict) -> str:
    """The recent rate and what it projects, or a plain statement that it cannot.

    The insufficient case renders as a sentence rather than a blank tile or a
    zero. A zero here would read as "no progress", which is a different claim
    from "not enough completions to measure a rate", and the page has no way to
    correct the reader afterwards.
    """
    velocity = data.get("velocity") or {}
    forecast = data.get("forecast") or {}
    window = velocity.get("window_days")
    if not window:
        return ""

    if not velocity.get("sufficient"):
        return (
            '\n<div class="forecast"><div><div class="label">Recent rate</div>'
            f'<div class="figure">—</div></div><div class="caveat">Only '
            f'{velocity.get("tasks", 0)} task(s) were completed in the last {window} days, '
            "which is not enough to measure a rate. The window is not widened to find data: "
            "a figure whose basis moved without saying so is worse than none."
            "</div></div>"
        )

    tiles = [
        ("Recent rate", f"{velocity['points_per_week']} pts/wk", f"last {window} days"),
        ("Remaining", f"{forecast.get('remaining_points', 0)} pts",
         f"{forecast.get('remaining_tasks', 0)} tasks"),
    ]
    if forecast.get("projected_date"):
        tiles.append(
            ("Projected finish", forecast["projected_date"],
             f"~{forecast['weeks_remaining']} weeks at this rate")
        )

    cells = "".join(
        f'<div><div class="label">{label}</div><div class="figure">{value}</div>'
        f'<div class="label">{sub}</div></div>'
        for label, value, sub in tiles
    )

    caveats = []
    if forecast.get("derived"):
        caveats.append(
            "This projection rests partly on model-assigned effort or git-inferred completion "
            "dates — see the note above."
        )
    if forecast.get("unestimated"):
        caveats.append(
            f"{len(forecast['unestimated'])} remaining task(s) carry no effort estimate, "
            "so the remaining total is an under-count."
        )
    caveat = f'<div class="caveat">{" ".join(caveats)}</div>' if caveats else ""
    return f'\n<div class="forecast">{cells}{caveat}</div>'


def _row(entry: dict, note: str = "", primary: bool = True) -> str:
    effort = f"{entry['effort']} pts" if isinstance(entry.get("effort"), int) else "no estimate"
    classes = "row" if primary else "row secondary"
    return (
        f'    <div class="{classes}"><span class="id">{escape(entry["id"])}</span>'
        f'<span>{escape(entry.get("title") or "")}</span>'
        f'<span class="note">{escape(effort)}{" · " + escape(note) if note else ""}</span></div>'
    )


def backlog_board(data: dict) -> str:
    """Batches, ready work, and what is waiting — the queue, without a terminal.

    Ordering and grouping arrive already decided in `readiness`; nothing here
    sorts or filters. Any ordering rule that appeared in this function rather
    than in the metrics document would be the beginning of this page disagreeing
    with `path status` and `tasks/index.md`.
    """
    ready = data.get("readiness") or {}
    if not ready or not ready.get("total"):
        return '  <p class="empty">No tasks yet.</p>'

    state = {
        entry["id"]: (group, entry)
        for group in ("ready", "waiting", "blocked", "in_progress", "complete")
        for entry in ready.get(group, [])
    }
    note_for = {
        "in_progress": "in progress",
        "blocked": "blocked",
        "complete": "done",
        "ready": "ready",
    }

    groups = []
    batched: set[str] = set()

    for batch in data.get("batches") or []:
        if batch["status"] == "complete":
            batched.update(batch["sequence"])
            continue
        rows = []
        for task_id in batch["sequence"]:
            batched.add(task_id)
            found = state.get(task_id)
            if not found:
                continue
            group, entry = found
            note = ", ".join(entry["needs"]) if group == "waiting" else note_for.get(group, "")
            note = f"needs {note}" if group == "waiting" else note
            rows.append(_row(entry, note, primary=group in ("ready", "in_progress")))
        groups.append(
            f'  <div class="board-group"><h3>{escape(batch["id"])} {escape(batch["title"])} '
            f'<span class="progress">— {batch["status"]}, {batch["tasks_done"]}/'
            f'{batch["tasks_total"]} tasks, {batch["points_done"]}/{batch["points_total"]} pts'
            "</span></h3>\n" + "\n".join(rows) + "</div>"
        )

    loose = []
    for group in ("in_progress", "ready", "blocked", "waiting"):
        for entry in ready.get(group, []):
            if entry["id"] in batched:
                continue
            note = (
                f"needs {', '.join(entry['needs'])}" if group == "waiting" else note_for[group]
            )
            loose.append(_row(entry, note, primary=group in ("ready", "in_progress")))
    if loose:
        groups.append(
            '  <div class="board-group"><h3>Not in a batch</h3>\n' + "\n".join(loose) + "</div>"
        )

    done = len(ready.get("complete", []))
    if done:
        groups.append(f'  <p class="empty">{done} task(s) complete.</p>')

    return "\n".join(groups)


def render_html(data: dict) -> str:
    html = HTML_TEMPLATE
    html = html.replace("__PROJECT__", data["project"])
    html = html.replace("__GENERATED__", data["generated"])
    html = html.replace("__PROVENANCE__", provenance_banner(data))
    html = html.replace("__FORECAST__", forecast_banner(data))
    html = html.replace("__BOARD__", backlog_board(data))
    html = html.replace("__DATA__", json.dumps(data))
    return html


def provenance_banner(data: dict) -> str:
    """Say so, on the page, when the numbers are not measurements.

    A reader who cannot tell an estimate from a recorded fact will treat both as
    evidence. Anything derived is declared here rather than in a comment nobody
    opens.
    """
    prov = data.get("provenance") or {}
    if not prov.get("any_derived"):
        return ""

    parts = []
    if prov.get("effort_estimated"):
        parts.append(
            f"{len(prov['effort_estimated'])} effort estimates were assigned retrospectively "
            "by a model, not recorded when the work was done"
        )
    if prov.get("completed_inferred"):
        parts.append(
            f"{len(prov['completed_inferred'])} completion dates were inferred from git commit "
            "dates, so they record when the file entered the repository rather than when the "
            "work finished"
        )
    return (
        '\n<div class="derived-note"><strong>Some of this is derived, not measured.</strong> '
        + "; ".join(parts)
        + ". Treat the shape of the early history as an artifact of the migration."
        + "</div>"
    )


def main() -> int:
    root = okf.find_project_root()
    if root is None:
        sys.exit("No Path project found here.")
    data = metrics.build(root)
    out_path = root / "status.html"
    out_path.write_text(render_html(data), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
