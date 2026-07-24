"""Project a SQLite memory index into a budgeted Markdown MEMORY.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Any

from qhaway.model import fetch_nodes


DEFAULT_BUDGET = 24_000
KNOWN_TYPES = ("user", "feedback", "project", "reference")
FOOTER_TYPES = KNOWN_TYPES
ENTRY_SEPARATOR = "\n"


def project_slice(
    db_conn: Any,
    budget: int,
    content_type: str | None = None,
    role: str | None = None,
    status: str = "live",
) -> str:
    """Return a deterministic, budgeted Markdown projection."""

    rows = [_normalize_row(node) for node in fetch_nodes(db_conn)]
    superseded_slugs = _superseded_slugs(db_conn)
    filtered = [
        row
        for row in rows
        if row["status"] == status
        and not _is_link_superseded(row, superseded_slugs, status)
        and (content_type is None or row["content_type"] == content_type)
        and (role is None or row["role"] == role)
    ]
    hidden_superseded = [
        row
        for row in rows
        if (
            row["status"] == "superseded"
            or _is_link_superseded(row, superseded_slugs, status)
        )
        and status == "live"
        and (content_type is None or row["content_type"] == content_type)
        and (role is None or row["role"] == role)
    ]

    ordered = sorted(filtered, key=cmp_to_key(_compare_rows))
    candidate_footer = _candidate_footer(filtered, hidden_superseded)
    fill_budget = max(0, budget - _byte_len(candidate_footer))

    included: list[dict[str, Any]] = []
    current = ""
    for row in ordered:
        proposed = _render_entries([*included, row])
        if _byte_len(proposed) <= fill_budget:
            included.append(row)
            current = proposed

    omitted = [row for row in filtered if row not in included]
    footer = _actual_footer(omitted, hidden_superseded)
    output = _join_lines([current, footer])
    if _byte_len(output) <= budget:
        return output

    # If the exact footer is larger than the pessimistic reserve due to unusual
    # type names or a tiny budget, remove entries until the declaration fits.
    while included and _byte_len(output) > budget:
        included.pop()
        omitted = [row for row in filtered if row not in included]
        output = _join_lines([_render_entries(included), _actual_footer(omitted, hidden_superseded)])

    if _byte_len(output) <= budget:
        return output

    return _fit_footer_only(_actual_footer(filtered, hidden_superseded), budget)


def _superseded_slugs(db_conn: Any) -> set[str]:
    """Slugs that any node declares it supersedes (SUPERSEDES edge targets).

    Tolerates a connection without an `edges` table (e.g. a hand-built
    nodes-only test fixture): no edges table => no link-supersession.
    """
    try:
        cursor = db_conn.execute(
            "SELECT DISTINCT dst_slug FROM edges WHERE kind = 'SUPERSEDES'"
        )
    except Exception:
        return set()
    return {row[0] for row in cursor.fetchall()}


def _is_link_superseded(row: dict[str, Any], superseded_slugs: set[str], status: str) -> bool:
    """A live node is link-superseded if something points a SUPERSEDES edge at it.

    Only demotes within a live slice — a node explicitly requested by
    status=superseded is shown as asked, never re-hidden.
    """
    if status != "live":
        return False
    stem = str(row["file"]).removesuffix(".md")
    return stem in superseded_slugs


def _normalize_row(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": values.get("file"),
        "name": values.get("name"),
        "content_type": values.get("content_type") or "project",
        "description": values.get("description"),
        "role": values.get("role"),
        "status": values.get("status") or "live",
        "origin_session": values.get("origin_session"),
        "date_hint": values.get("date_hint"),
        "body": values.get("body") or "",
        "mtime_ns": values.get("mtime_ns") or 0,
    }


def _compare_rows(left: dict[str, Any], right: dict[str, Any]) -> int:
    priority_cmp = _priority(left) - _priority(right)
    if priority_cmp:
        return priority_cmp
    for key in ("date_hint", "origin_session"):
        cmp = _compare_desc_string(left.get(key), right.get(key))
        if cmp:
            return cmp
    return (left["file"] > right["file"]) - (left["file"] < right["file"])


def _priority(row: dict[str, Any]) -> int:
    return 0 if row["content_type"] in {"user", "feedback"} else 1


def _compare_desc_string(left: Any, right: Any) -> int:
    if left and not right:
        return -1
    if right and not left:
        return 1
    if not left and not right:
        return 0
    left_text = str(left)
    right_text = str(right)
    return (right_text > left_text) - (right_text < left_text)


def _entry_line(row: dict[str, Any]) -> str:
    title = _title(row)
    hook = _hook(row)
    return f"- [{title}]({row['file']}) — {hook}"


def _render_entries(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    lines: list[str] = []
    for content_type in _section_order(rows):
        group = [row for row in rows if row["content_type"] == content_type]
        if not group:
            continue
        lines.append(f"## {_section_title(content_type)}")
        lines.extend(_entry_line(row) for row in group)
    return _join_lines(lines)


def _section_order(rows: list[dict[str, Any]]) -> list[str]:
    present = {row["content_type"] for row in rows}
    ordered = [content_type for content_type in KNOWN_TYPES if content_type in present]
    ordered.extend(sorted(present.difference(KNOWN_TYPES)))
    return ordered


def _section_title(content_type: str) -> str:
    return content_type.replace("_", " ").title()


def _title(row: dict[str, Any]) -> str:
    name = row.get("name")
    if name and str(name).strip().upper() not in {"SUPERSEDED", "DELETED"}:
        return str(name).strip()
    return str(row["file"]).removesuffix(".md").replace("_", " ").title()


def _hook(row: dict[str, Any]) -> str:
    description = row.get("description")
    if description:
        return _one_line(description)
    body = row.get("body") or ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return _one_line(stripped)
    return _title(row)


def _one_line(text: Any, limit: int = 140) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _candidate_footer(filtered: list[dict[str, Any]], hidden_superseded: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in filtered:
        counts[row["content_type"]] = counts.get(row["content_type"], 0) + 1
    lines = [
        _omission_line(content_type, count)
        for content_type, count in _ordered_counts(counts)
        if count > 0
    ]
    if hidden_superseded:
        lines.append(_superseded_line(len(hidden_superseded)))
    return _join_lines(lines)


def _actual_footer(omitted: list[dict[str, Any]], hidden_superseded: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in omitted:
        counts[row["content_type"]] = counts.get(row["content_type"], 0) + 1
    lines = [
        _omission_line(content_type, count)
        for content_type, count in _ordered_counts(counts)
        if count > 0
    ]
    if hidden_superseded:
        lines.append(_superseded_line(len(hidden_superseded)))
    return _join_lines(lines)


def _ordered_counts(counts: dict[str, int]) -> list[tuple[str, int]]:
    ordered = [(content_type, counts[content_type]) for content_type in FOOTER_TYPES if content_type in counts]
    ordered.extend(sorted((key, value) for key, value in counts.items() if key not in FOOTER_TYPES))
    return ordered


def _omission_line(content_type: str, count: int) -> str:
    return f"+{count} {content_type} memories not shown; `qhaway index --type {content_type}`"


def _superseded_line(count: int) -> str:
    return f"+{count} superseded memories hidden; `qhaway index --status superseded`"


def _join_lines(lines: Any) -> str:
    normalized = [line for line in lines if line]
    return ENTRY_SEPARATOR.join(normalized) + ("\n" if normalized else "")


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _fit_footer_only(footer: str, budget: int) -> str:
    if _byte_len(footer) <= budget:
        return footer
    output = ""
    for line in footer.splitlines():
        proposed = _join_lines([output, line])
        if _byte_len(proposed) <= budget:
            output = proposed
    return output


@dataclass
class Overflow:
    """Structured overflow of a budgeted projection.

    `omitted_counts` maps content_type -> count of nodes that matched the slice
    filter but did not fit the budget. `superseded_count` is the number of
    superseded nodes hidden from a live slice. Band counts (by origin_session /
    date_hint) are computed and carried for the deferred dynamic-faceting step.
    """

    omitted_counts: dict = field(default_factory=dict)
    superseded_count: int = 0
    by_origin_session: dict = field(default_factory=dict)
    by_date_hint: dict = field(default_factory=dict)


@dataclass
class ProjectionResult:
    markdown: str
    overflow: Overflow = field(default_factory=Overflow)


def project_slice_with_overflow(
    db_conn: Any,
    budget: int,
    content_type: str | None = None,
    role: str | None = None,
    status: str = "live",
) -> ProjectionResult:
    """Render the slice AND return structured overflow counts (C-1/F-7)."""
    markdown = project_slice(db_conn, budget, content_type, role, status)
    rows = [_normalize_row(node) for node in fetch_nodes(db_conn)]
    superseded_slugs = _superseded_slugs(db_conn)
    filtered = [
        row
        for row in rows
        if row["status"] == status
        and not _is_link_superseded(row, superseded_slugs, status)
        and (content_type is None or row["content_type"] == content_type)
        and (role is None or row["role"] == role)
    ]
    omitted = [row for row in filtered if f"]({row['file']})" not in markdown]
    omitted_counts: dict = {}
    for row in omitted:
        omitted_counts[row["content_type"]] = omitted_counts.get(row["content_type"], 0) + 1

    superseded_count = sum(
        1
        for row in rows
        if (
            row["status"] == "superseded"
            or _is_link_superseded(row, superseded_slugs, status)
        )
        and status == "live"
        and (content_type is None or row["content_type"] == content_type)
        and (role is None or row["role"] == role)
    )

    overflow = Overflow(
        omitted_counts=omitted_counts,
        superseded_count=superseded_count,
        by_origin_session=_band(omitted, "origin_session"),
        by_date_hint=_band(omitted, "date_hint"),
    )
    return ProjectionResult(markdown=markdown, overflow=overflow)


def _band(rows: list[dict[str, Any]], key: str) -> dict:
    counts: dict = {}
    for row in rows:
        value = row.get(key) or "(none)"
        counts[value] = counts.get(value, 0) + 1
    return counts
