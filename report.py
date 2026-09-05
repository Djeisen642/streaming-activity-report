"""Renders report.html: a single self-contained, dark-themed HTML file."""
import html
from datetime import date
from typing import List, Optional

import config
from models import PlatformResult


# How the "last activity" figure for a platform was obtained:
#   "watched"     — a real per-item watch date (Netflix, Prime Video)
#   "list-change" — the date this platform's "Continue Watching" rail was
#                   last seen to change (Hulu, Disney+ — they publish no
#                   watch dates); derived across runs by snapshots.py
#   "unknown"     — no signal at all (fetch errored, or first-ever run)
def _activity(result: PlatformResult) -> "tuple[str, Optional[date]]":
    dated = [e.watched_date for e in result.events if e.watched_date is not None]
    if dated:
        return "watched", max(dated)
    if result.last_activity_date is not None:
        return "list-change", result.last_activity_date
    return "unknown", None


def _idle_days(when: Optional[date], today: date) -> Optional[int]:
    if when is None:
        return None
    return (today - when).days


def _fmt_date(d: Optional[date]) -> str:
    return d.strftime("%Y-%m-%d") if d else "Unknown"


def _fmt_idle(idle: Optional[int]) -> str:
    return f"{idle}d" if idle is not None else "Unknown"


_BASIS_MARK = {"list-change": " ↻", "watched": "", "unknown": ""}


def build_report(results: List[PlatformResult], today: Optional[date] = None) -> str:
    today = today or date.today()

    rows = []
    for r in results:
        basis, when = _activity(r)
        rows.append(
            {
                "platform": r.platform,
                "last_watched": when,
                "basis": basis,
                "idle_days": _idle_days(when, today),
                "count": len(r.events),
                "profile": r.profile,
                "error": r.error,
            }
        )

    # Rank by idle days descending (most-neglected first). Platforms with
    # no signal at all — a fetch that errored, or a first-ever run with no
    # snapshot baseline yet — sort to the bottom as "unknown" rather than
    # falsely reading as most-idle or most-active. A "list-change" date
    # ranks alongside real watch dates; it's a coarser number but the same
    # question ("how long since anything happened here").
    known_rows = sorted(
        (row for row in rows if row["idle_days"] is not None),
        key=lambda row: row["idle_days"],
        reverse=True,
    )
    unknown_rows = [row for row in rows if row["idle_days"] is None]
    table_rows = known_rows + unknown_rows

    card_rows = sorted(rows, key=lambda row: row["platform"])

    return _PAGE_TEMPLATE.format(
        generated_at=today.strftime("%Y-%m-%d"),
        idle_threshold=config.IDLE_THRESHOLD_DAYS,
        cards="\n".join(_render_card(row) for row in card_rows),
        table_rows="\n".join(_render_table_row(row) for row in table_rows),
    )


def _is_idle_flagged(row: dict) -> bool:
    return row["idle_days"] is not None and row["idle_days"] > config.IDLE_THRESHOLD_DAYS


def _profile_note(row: dict) -> str:
    if not row["profile"]:
        return ""
    return (
        f'<p class="card-note">Profile checked: {html.escape(row["profile"])} '
        f'(this account\'s other profiles not counted)</p>'
    )


def _render_card(row: dict) -> str:
    platform = html.escape(row["platform"])
    classes = "card card-idle" if _is_idle_flagged(row) else "card"

    if row["error"]:
        body = f'<p class="card-error">Fetch failed: {html.escape(row["error"])}</p>'
    elif row["basis"] == "list-change":
        body = (
            f'<p><span class="label">Continue Watching last changed:</span> '
            f'{_fmt_date(row["last_watched"])}</p>'
            f'<p><span class="label">Unchanged for:</span> {_fmt_idle(row["idle_days"])}</p>'
            f'<p><span class="label">In Continue Watching:</span> {row["count"]}</p>'
            f'<p class="card-note">No watch dates published; activity inferred from '
            f'run-to-run changes.</p>'
            f'{_profile_note(row)}'
        )
    else:
        body = (
            f'<p><span class="label">Last watched:</span> {_fmt_date(row["last_watched"])}</p>'
            f'<p><span class="label">Titles found:</span> {row["count"]}</p>'
            f'<p><span class="label">Idle:</span> {_fmt_idle(row["idle_days"])}</p>'
            f'{_profile_note(row)}'
        )

    return f'<div class="{classes}"><h2>{platform}</h2>{body}</div>'


def _render_table_row(row: dict) -> str:
    row_class = ' class="row-idle"' if _is_idle_flagged(row) else ""
    platform = html.escape(row["platform"])
    error_suffix = (
        f' <span class="cell-error">({html.escape(row["error"])})</span>' if row["error"] else ""
    )
    date_cell = _fmt_date(row["last_watched"]) + _BASIS_MARK.get(row["basis"], "")

    return (
        f"<tr{row_class}>"
        f"<td>{platform}</td>"
        f"<td>{date_cell}</td>"
        f"<td>{_fmt_idle(row['idle_days'])}</td>"
        f"<td>{row['count']}{error_suffix}</td>"
        f"</tr>"
    )


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Streaming Usage Audit</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #0f1115;
    --surface: #171a21;
    --surface-alt: #1e222b;
    --border: #2a2f3a;
    --text: #e6e8eb;
    --text-dim: #9aa1ac;
    --idle: #ff6b6b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 2rem;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  h1 {{ margin-top: 0; }}
  .meta {{ color: var(--text-dim); margin-bottom: 2rem; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.25rem;
  }}
  .card h2 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; }}
  .card p {{ margin: 0.25rem 0; font-size: 0.9rem; color: var(--text-dim); }}
  .card .label {{ color: var(--text); }}
  .card-note {{ font-size: 0.8rem; font-style: italic; opacity: 0.8; margin-top: 0.5rem; }}
  .card-idle {{ border-color: var(--idle); box-shadow: 0 0 0 1px var(--idle); }}
  .card-error {{ color: var(--idle); }}
  .footnote {{ color: var(--text-dim); font-size: 0.8rem; margin-top: 1rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }}
  th, td {{
    text-align: left;
    padding: 0.65rem 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
  }}
  th {{ background: var(--surface-alt); color: var(--text-dim); font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  tr.row-idle td:first-child {{ box-shadow: inset 3px 0 0 var(--idle); }}
  .cell-error {{ color: var(--idle); font-size: 0.85rem; }}
</style>
</head>
<body>
  <h1>Streaming Usage Audit</h1>
  <p class="meta">Generated {generated_at} &middot; idle threshold: {idle_threshold} days</p>

  <div class="cards">
{cards}
  </div>

  <table>
    <thead>
      <tr><th>Platform</th><th>Last watched</th><th>Idle</th><th>Titles</th></tr>
    </thead>
    <tbody>
{table_rows}
    </tbody>
  </table>
  <p class="footnote">&#8635; = no watch date published by the platform; the
  date shown is when its &ldquo;Continue Watching&rdquo; list was last seen to
  change between runs, so its precision is only as fine as how often this tool
  runs.</p>
</body>
</html>
"""
