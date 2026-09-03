"""Field report from the first instance on 0.5.x (2026-09-03): the projection
put a stale memory at the frontier and a supersession didn't demote its target.
Three mechanisms, each pinned here:

1. The slug cap (0.5.0) broke supersession against pre-cap files: targets are
   normalized through slugify (which now caps+hashes long stems), but the
   projection compared raw file stems to edge slugs — a capped edge can never
   match a long stem. Both sides must meet through the same normalization.
2. Dates written as month-name kebab (`sep-3-2026`) never populated date_hint,
   so recency ordering silently degraded to the filename tie-break.
3. With no date_hint at all, the tie-break was alphabetical — an arbitrary
   order presented as a frontier. Newer mtime must outrank older before the
   filename fallback.
"""

from __future__ import annotations

from pathlib import Path

from qhaway import model, project, reconcile, server


LONG_TITLE = (
    "M1 evidence map v4 written Sep 1 2026 witness 11 is the single item gating "
    "the PIs D1 Part C selection candidate region 14 12 2 where Q1 Q5 gaps are "
    "exactly zero overflowing the slug cap but not the filesystem"
)


def _precap_stem(title: str) -> str:
    # The pre-0.5.0 slug rule: no cap. Reproduce it so the fixture matches what
    # old stores actually hold on disk.
    lowered = title.strip().lower().replace(" ", "-")
    return reconcile._SLUG_COLLAPSE.sub("-", reconcile._SLUG_STRIP.sub("", lowered)).strip("-")


def test_capped_supersedes_target_demotes_a_precap_file(tmp_path):
    stem = _precap_stem(LONG_TITLE)
    assert len(stem.encode("utf-8")) > reconcile._SLUG_MAX  # fixture is really pre-cap
    (tmp_path / f"{stem}.md").write_text(
        f"---\nname: {LONG_TITLE}\ntype: project\ndescription: stale frontier\n---\nold\n",
        encoding="utf-8",
    )

    server.remember(
        "project", "Witness 11 searched", "new frontier",
        description="supersedes the stale map", supersedes=stem, memory_dir=str(tmp_path),
    )

    conn = model.get_connection(str(tmp_path))
    try:
        out = project.project_slice(conn, budget=8000)
    finally:
        conn.close()
    assert "Witness 11 searched" in out
    assert "stale frontier" not in out  # demoted, not still presented live
    assert "superseded memories hidden" in out


def test_precap_supersedes_link_demotes_a_capped_file(tmp_path):
    # The mirror image: an old file's long [[wikilink]] must still demote a
    # target whose on-disk stem was written capped.
    capped = reconcile.slugify(LONG_TITLE)
    (tmp_path / f"{capped}.md").write_text(
        f"---\nname: {LONG_TITLE}\ntype: project\ndescription: capped target\n---\nold\n",
        encoding="utf-8",
    )
    stem = _precap_stem(LONG_TITLE)
    (tmp_path / "newer-note.md").write_text(
        "---\nname: newer note\ntype: project\ndescription: the correction\n"
        f"supersedes:\n- '[[{stem}]]'\n---\nnew\n",
        encoding="utf-8",
    )

    reconcile.reconcile(str(tmp_path))
    conn = model.get_connection(str(tmp_path))
    try:
        out = project.project_slice(conn, budget=8000)
    finally:
        conn.close()
    assert "the correction" in out
    assert "capped target" not in out


def test_month_name_kebab_dates_populate_date_hint(tmp_path):
    f = tmp_path / "witness-11-searched-sep-3-2026-commit-04cef86.md"
    f.write_text("---\nname: w11\ntype: project\n---\nbody\n", encoding="utf-8")

    from qhaway import parse
    assert parse.parse_memory_file(str(f))["date_hint"] == "20260903"


def test_month_name_date_orders_against_dashed_date(tmp_path):
    # Cross-format recency: a month-name-dated stem must outrank an older
    # ISO-dashed one, and alphabet must not decide. (The index stays a pure
    # function of content — test_cli_idempotence pins that mtime must NOT
    # order it, so recency rides date_hint, never stat.)
    (tmp_path / "a-map-written-2026-09-01-alphabetically-first.md").write_text(
        "---\nname: older map\ntype: project\ndescription: older\n---\nb\n", encoding="utf-8"
    )
    (tmp_path / "witness-11-searched-sep-3-2026.md").write_text(
        "---\nname: newer witness\ntype: project\ndescription: newer\n---\nb\n", encoding="utf-8"
    )

    reconcile.reconcile(str(tmp_path))
    conn = model.get_connection(str(tmp_path))
    try:
        out = project.project_slice(conn, budget=8000)
    finally:
        conn.close()
    assert out.index("newer witness") < out.index("older map")
