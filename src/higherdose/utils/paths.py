from __future__ import annotations

"""Filesystem helper utilities used across the HigherDOSE code-base.

This module intentionally has **zero** external dependencies so that it can
be imported early (e.g. from lightweight scripts in `scripts/`).
"""

from pathlib import Path
from typing import Iterable, Sequence


# ---------------------------------------------------------------------------
# 🔍  Repository-aware path helpers
# ---------------------------------------------------------------------------


def _looks_like_repo_root(path: Path, markers: Sequence[str]) -> bool:
    """Return ``True`` if *path* contains any of the *marker* files/dirs."""
    for marker in markers:
        if (path / marker).exists():
            return True
    return False


def project_root(markers: Sequence[str] | None = None) -> Path:
    """Return the absolute ``Path`` of the repo root.

    The function walks *up* from *this* file until it discovers a directory
    that contains at least one *marker* (default: ``pyproject.toml`` or
    ``.git``).  If none is found we fall back to two parents above this file
    so that execution continues gracefully even in unusual layouts (e.g. when
    the code lives inside a zipfile or temp directory).
    """
    if markers is None:
        markers = ("pyproject.toml", ".git")

    cur = Path(__file__).resolve()
    for parent in [cur] + list(cur.parents):
        if _looks_like_repo_root(parent, markers):
            return parent
    # Fallback: assume utils/paths.py is at ``src/higherdose/utils/`` so two
    # parents up should be the project root.
    return cur.parents[2]


def find_latest_in_repo(pattern: str, markers: Sequence[str] | None = None) -> str | None:
    """Return the *newest* file matching *pattern* anywhere inside the repo.

    Parameters
    ----------
    pattern : str
        Unix-shell wildcard pattern (e.g. ``"google-2024*-daily*.csv"``).
    markers : Sequence[str] | None, optional
        Override the *project_root* marker list if required.

    Notes
    -----
    • The search is *recursive* (`Path.rglob`) so performance is O(number of
      files). If your repo is *very* large you may want to narrow the search
      by first identifying likely top-level directories.
    • Returns ``None`` when no match is found so callers must handle that case.
    """
    root = project_root(markers)
    matches: Iterable[Path] = root.rglob(pattern)
    latest: Path | None = None
    latest_mtime = -1.0
    for p in matches:
        try:
            mtime = p.stat().st_mtime
        except (FileNotFoundError, PermissionError):
            continue  # Skip paths we cannot stat
        if mtime > latest_mtime:
            latest = p
            latest_mtime = mtime
    return str(latest) if latest else None


__all__ = [
    "project_root",
    "find_latest_in_repo",
] 