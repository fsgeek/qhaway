"""Parse Markdown topic files into qhaway memory nodes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


TOMBSTONE_NAMES = {"SUPERSEDED", "DELETED"}
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:[|#][^\]]*)?\]\]")
DATE_RE = re.compile(r"(?:^|_)(\d{8})(?:_|$)")


def parse_memory_file(filepath: str) -> dict[str, Any]:
    """Parse one topic Markdown file.

    The real corpora contain imperfect frontmatter. This parser tries YAML first,
    falls back to a tolerant line parser, and always returns a body-only node if
    metadata parsing fails.
    """

    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    metadata, body, parse_warning = _split_frontmatter(text)
    name = _string_or_none(metadata.get("name"))
    content_type = _string_or_none(metadata.get("type"))
    origin_session = _origin_session(metadata)
    date_hint = _date_hint(path.stem, metadata)

    return {
        "file": path.name,
        "name": name,
        "content_type": content_type,
        "role": _role(path.stem),
        "status": _status(name),
        "origin_session": origin_session,
        "date_hint": date_hint,
        "description": _string_or_none(metadata.get("description")),
        "body": body,
        "links": [_normalize_link(match) for match in WIKILINK_RE.findall(body)],
        "parse_warning": parse_warning,
    }


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str, str | None]:
    if not text.startswith("---"):
        return {}, text, None

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, None

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return {}, text, "frontmatter opener had no closing delimiter; indexed as body-only"

    raw_frontmatter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])
    try:
        loaded = yaml.safe_load(raw_frontmatter) or {}
        if isinstance(loaded, dict):
            return loaded, body, None
    except yaml.YAMLError:
        pass

    return _tolerant_frontmatter(raw_frontmatter), body, "frontmatter parsed with tolerant fallback"


def _tolerant_frontmatter(raw_frontmatter: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key:
            metadata[key] = value.strip().strip("\"'")
    return metadata


def _origin_session(metadata: dict[str, Any]) -> str | None:
    direct = _string_or_none(metadata.get("originSessionId"))
    if direct:
        return direct
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        return _string_or_none(nested.get("originSessionId"))
    return None


def _date_hint(stem: str, metadata: dict[str, Any]) -> str | None:
    for key in ("date_hint", "dateHint", "date"):
        value = _string_or_none(metadata.get(key))
        if value:
            return _normalize_date(value)
    match = DATE_RE.search(stem)
    if match:
        return match.group(1)
    return None


def _normalize_date(value: str) -> str:
    dashed = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if dashed:
        return "".join(dashed.groups())
    return value


def _role(stem: str) -> str | None:
    if "_" not in stem:
        return None
    prefix = stem.split("_", 1)[0]
    return prefix or None


def _status(name: str | None) -> str:
    if name and name.strip().upper() in TOMBSTONE_NAMES:
        return "superseded"
    return "live"


def _normalize_link(link: str) -> str:
    cleaned = link.strip().split("/", maxsplit=-1)[-1]
    if cleaned.endswith(".md"):
        cleaned = cleaned[:-3]
    return cleaned


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
