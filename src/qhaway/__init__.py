"""qhaway — a truncation-proof projection of a Markdown memory index.

See the design spec: docs/superpowers/specs/2026-06-20-qhaway-mvp-design.md
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("qhaway")
except PackageNotFoundError:  # not installed (e.g. running from a bare checkout)
    __version__ = "0.0.0+unknown"
