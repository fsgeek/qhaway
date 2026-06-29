"""MCP spine: the remember/recall verbs over the existing pipeline."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from qhaway import cli, model, project, reconcile

VALID_TYPES = {"user", "feedback", "project", "reference"}
_MAX_SUFFIX = 100
_EVENT_LOG = "events.jsonl"


def _emit(root: Path, event: dict) -> None:
    """Append one event as a single line. O_APPEND => kernel-serialized, no
    coordination across concurrent writers; one write under PIPE_BUF stays atomic.
    Metadata only — never the body. Observability must never break a verb, so
    failures here are swallowed. See [[single-writer-summons-consensus]]."""
    event.setdefault("ts", time.time())
    event.setdefault("session_id", os.environ.get("QHAWAY_SESSION_ID"))
    line = json.dumps(event, separators=(",", ":")) + "\n"
    try:
        fd = os.open(str(root / _EVENT_LOG), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def remember(type, title, body, description=None, links=None, memory_dir=".") -> str:
    if type not in VALID_TYPES:
        raise ValueError(f"invalid type {type!r}; must be one of {sorted(VALID_TYPES)}")
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")

    text = reconcile.compose_topic_file(type, title, body, description, links)
    stem = reconcile.slugify(title)
    filename = _exclusive_write(root, stem, text)
    reconcile.reconcile(str(root))
    _emit(root, {"verb": "remember", "type": type, "title": title,
                 "body_chars": len(body), "filename": filename})
    return filename


def _exclusive_write(root: Path, stem: str, text: str) -> str:
    for suffix in range(0, _MAX_SUFFIX):
        name = f"{stem}.md" if suffix == 0 else f"{stem}-{suffix}.md"
        path = root / name
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return name
    raise RuntimeError(
        f"could not allocate a unique topic filename for {stem!r} after {_MAX_SUFFIX} attempts"
    )


def recall(type=None, role=None, status="live", memory_dir=".", reground=None) -> str:
    """Project the memory slice; if `reground` is injected, re-ground any claim.

    `reground` is an optional callable taking a claim dict and returning a live
    rendered string (yanantin supplies it; qhaway never imports the DB layer —
    dependency inversion, see 2026-06-28-claim-regrounding-at-recall-design.md).
    Without it, or absent any claim, the projection is byte-identical to before.
    """
    root = Path(memory_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"memory directory is not readable: {memory_dir}")
    conn = model.get_connection(str(root))
    try:
        result = project.project_slice_with_overflow(
            conn, budget=project.DEFAULT_BUDGET, content_type=type, role=role, status=status
        )
        claims = _claim_nodes(conn, type, role, status) if reground is not None else []
    finally:
        conn.close()
    markdown = result.markdown
    if claims:
        markdown = markdown.rstrip() + "\n\n" + _render_regroundings(claims, reground) + "\n"
    _emit(root, {"verb": "recall", "type": type, "role": role, "status": status,
                 "result_chars": len(markdown)})
    return markdown


def _claim_nodes(conn, content_type, role, status) -> list[dict]:
    """Claim-bearing nodes within the SAME slice the projection shows — re-grounding
    must respect the recall filter (type/role/status), not leak claims from
    memories outside the projected set. Normalizes content_type/status the way the
    projection does (project._normalize_row) so the two slices agree exactly."""
    return [
        node for node in model.fetch_nodes(conn)
        if node.get("claim")
        and (node.get("status") or "live") == status
        and (content_type is None or (node.get("content_type") or "project") == content_type)
        and (role is None or node.get("role") == role)
    ]


def _render_regroundings(claims: list[dict], reground) -> str:
    """One re-grounded line per claim-bearing memory — staleness made legible at
    recall. The frozen value lives in the body; reground returns the live one."""
    lines = ["## Re-grounded claims"]
    for node in claims:
        live = reground(node["claim"])
        lines.append(f"- [{node.get('name') or node['file']}]({node['file']}): {live}")
    return "\n".join(lines)


def initialize_server(memory_dir: str) -> None:
    """Run exactly one reconcile at startup, before accepting tool calls (C-3)."""
    cli.reconcile(memory_dir)


def run(memory_dir: str) -> None:
    """The blocking MCP event loop: expose remember/recall as live tools (stdio).

    Built per the handoff [[handoff-serve-is-the-last-stub]] — this is the last
    limb. The verbs already exist above; this binds them to the memory dir and
    runs the protocol loop a Claude Code session connects to.
    """
    from mcp.server.fastmcp import FastMCP

    initialize_server(memory_dir)
    mcp = FastMCP("qhaway")

    @mcp.tool()
    def recall(type=None, role=None, status="live") -> str:
        """Read your memory: a budgeted projection of the structured store, not
        the whole file. Omit args for the working set; filter by `type`
        (user/feedback/project/reference), `role`, or `status`."""
        return _recall_impl(type, role, status, memory_dir)

    @mcp.tool()
    def remember(type, title, body, description=None, links=None) -> str:
        """Write a memory to the structured store. `type` is one of
        user/feedback/project/reference. Returns the topic filename written."""
        return _remember_impl(type, title, body, description, links, memory_dir)

    mcp.run()


# Module-level aliases so the tool wrappers above call the real verbs without
# shadowing themselves inside run()'s local scope.
_recall_impl = recall
_remember_impl = remember


if __name__ == "__main__":
    run(os.environ.get("QHAWAY_MEMORY_DIR", "."))
