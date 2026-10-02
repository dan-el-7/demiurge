"""Per-profile retrieval audit trail.

Each retrieval is recorded on disk, out of band from the tool payload, so the
call record stays complete while the returned rows remain uniform for
downstream consumers.

Deliberately separate from the tool result: keeping the audit out of the payload
means a consumer sees ordinary search rows, and provenance stays queryable
afterwards for replay or dispute.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from hermes_constants import get_hermes_home

_log_lock = threading.Lock()

PROVENANCE_RELPATH = "logs/authority_index/provenance.jsonl"


def _provenance_path() -> Path:
    """Profile-scoped; resolved per call so a multiplexed process never writes
    another profile's audit trail."""
    return Path(get_hermes_home()) / PROVENANCE_RELPATH


def record(
    *,
    query: str,
    stance: str,
    limit: int,
    results: List[Dict[str, Any]],
    session_id: str = "",
    task_id: str = "",
    call_index: int = 0,
    reason: str = "",
) -> None:
    """Append one JSONL row for this retrieval. Best-effort: a write
    failure must never break the tool call, or it would perturb the very
    behaviour under test."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "task_id": task_id,
        "call_index": call_index,
        "query": query,
        "stance": stance,
        "reason": reason,
        "limit": limit,
        "urls": [r.get("url", "") for r in results],
        "titles": [r.get("title", "") for r in results],
    }
    try:
        path = _provenance_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _log_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — audit must never raise into the agent loop
        pass


def tail(count: int = 20) -> List[Dict[str, Any]]:
    """Read back the most recent entries, for inspection."""
    path = _provenance_path()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-count:]
