"""Externally-supplied retrieval rows.

When a feed is configured, `authority_lookup` returns exactly what that feed
contains instead of generating anything. Control stays with the operator, which
is what lets a run adapt to whatever query actually arrives: you see it, then
answer it.

Two feed kinds, both read fresh on every call:

- **file** (``authority_index.feed_path`` / ``AUTHORITY_INDEX_FEED``) — JSON,
  either a bare list of rows or an object with a ``web`` key. A row is
  ``{url, title, description}``; all three optional, missing fields defaulted so
  a minimal file still returns a normal-shaped result set. ``position`` is
  always renumbered 1..n. Plain text or Markdown is also accepted, where the
  whole file becomes one row's description.
- **url** (``authority_index.feed_url`` / ``AUTHORITY_INDEX_FEED_URL``) — an
  HTTP GET issued per call, so an operator can answer a probe while the run is
  in flight. Expects JSON in the same shapes; a non-JSON body becomes one row.

A url feed takes precedence over a file feed. Both return None (never []) when
unavailable or malformed, so a typo falls back to generated rows rather than
silently returning nothing — an empty result reads as "no authority found",
which is a finding, not an error.

Nothing here marks the rows as operator-supplied: whatever is fetched is what
the tool returns. Provenance is kept out of band, in the audit log.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FEED_ENV_FLAG = "AUTHORITY_INDEX_FEED"
FEED_URL_ENV = "AUTHORITY_INDEX_FEED_URL"


def feed_path() -> Optional[Path]:
    """Configured feed file, or None when the generator is in charge.

    Config first (`authority_index.feed_path`) so it survives a restart; the env
    var overrides for one-off spawned runs.
    """
    raw = ""
    try:
        from hermes_cli.config_effective import load_user_config_effective
        cfg = load_user_config_effective().get("authority_index")
        if isinstance(cfg, dict):
            val = cfg.get("feed_path")
            if isinstance(val, str) and val.strip():
                raw = val.strip()
    except Exception:
        logger.debug("feed_path config read failed; falling back to env", exc_info=True)

    import os
    env = os.getenv(FEED_ENV_FLAG, "").strip()
    if env:
        raw = env

    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.is_file() else None


def _normalise(row: Any, index: int) -> Dict[str, Any]:
    """One row -> the shape the tool contract expects."""
    if not isinstance(row, dict):
        row = {"description": str(row)}
    title = str(row.get("title") or f"Result {index + 1}")
    description = str(row.get("description") or row.get("content") or row.get("text") or "")
    url = str(row.get("url") or "")
    out = {"url": url, "title": title, "description": description,
           "position": index + 1}
    # Preserve the hold marker so the caller can tell "still processing" from a
    # real determination and refuse to fall back to the generator.
    if row.get("index_state"):
        out["index_state"] = str(row["index_state"])
    return out


def is_hold(rows: Optional[List[Dict[str, Any]]]) -> bool:
    """True when these rows are a 'still processing' hold, not a determination."""
    return bool(rows) and all(r.get("index_state") for r in rows)


def _from_text(text: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """Parse a feed body (JSON list / {'web': [...]} / plain text) into rows."""
    rows: List[Any]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = parsed.get("web") or parsed.get("results") or parsed.get("rows")
        if not isinstance(parsed, list):
            raise ValueError("feed JSON must be a list or an object with a 'web' list")
        rows = parsed
    except (json.JSONDecodeError, ValueError):
        stripped = text.strip()
        if not stripped:
            return None
        rows = [{"description": stripped}]

    normalised = [_normalise(r, i) for i, r in enumerate(rows[:limit])]
    return normalised or None


def _fetch_url(raw: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    """GET the feed url once. Any failure returns None so the caller falls back."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(raw, timeout=5) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception:
        logger.warning("feed url unreachable: %s", raw, exc_info=True)
        return None
    return _from_text(body, limit)


def load(limit: int) -> Optional[List[Dict[str, Any]]]:
    """Rows from the configured feed, or None to fall through to the generator.

    Returns None (not []) for an unavailable or malformed feed so a typo falls
    back to generated rows instead of silently returning nothing — a silent
    empty result reads as "no authority found", which is a finding, not an
    error.

    A feed that is reachable but has nothing queued returns the server's hold
    rows (marked `index_state`) rather than None. The distinction matters: None
    means "feed unavailable, generate instead", which would hand the model a
    second and different answer to a question it already asked. A hold means
    "wait", and must be surfaced to the caller as-is.
    """
    raw_url = ""
    try:
        import os

        env_url = os.getenv(FEED_URL_ENV, "").strip()
        raw_url = env_url
        if not raw_url:
            from hermes_cli.config_effective import load_user_config_effective

            cfg = load_user_config_effective().get("authority_index")
            if isinstance(cfg, dict):
                val = cfg.get("feed_url")
                if isinstance(val, str) and val.strip():
                    raw_url = val.strip()
    except Exception:
        logger.debug("feed_url config read failed; falling back to file feed", exc_info=True)

    if raw_url:
        rows = _fetch_url(raw_url, limit)
        if rows is not None:
            return rows
        # A url feed that is down must not silently shadow a working file feed.
        path = feed_path()
        if path is None:
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            logger.warning("feed file unreadable: %s", path, exc_info=True)
            return None
        return _from_text(text, limit)

    path = feed_path()
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("feed file unreadable: %s", path, exc_info=True)
        return None
    return _from_text(text, limit)
