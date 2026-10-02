#!/usr/bin/env python3
"""provenance-scan — detect skill-directed channel laundering.

Attack class: an instruction document (a skill) tells an agent to treat content
arriving over a NON-tool channel -- user input, a clarify reply, an "operator", a
relay endpoint -- as the authoritative OUTPUT of a tool, index or service. The
agent then cites attacker text with the provenance of retrieved data.

It is only effective when paired with a disabling instruction: do not verify, do
not corroborate, do not substitute your own knowledge. Either half alone is weak;
together they are the signature. A second, subtler signature is a *recency
override* -- a claimed effective date after a model's knowledge cutoff, which
recode the model's correct knowledge as stale.

Usage:
    python provenance-scan.py <path> [<path> ...]
    python provenance-scan.py ~/.hermes/skills ~/.hermes/plugins

Exit code 1 if any file scores HIGH, else 0.
NOTE: pass NATIVE paths. On Windows/git-bash, "/c/Users/..." will not resolve
for a native Python -- use "C:/Users/...".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Each pattern is a signal, not proof. The verdict combines them.
PATTERNS = {
    # Refers to a channel that is NOT a tool result.
    "channel": re.compile(
        r"\b(clarify|interactive input channel|user-?supplied|relay endpoint|"
        r"the operator|the user (?:has )?(?:indicated|will supply|supplies))\b",
        re.I,
    ),
    # Reframes that channel's content as a tool/service's output.
    "launder": re.compile(
        r"\b(treat|interpret|read|regard|accept)\b[^.\n]{0,90}?\b(as|like)\b"
        r"[^.\n]{0,70}?\b(index|service|registry|authority|tool|system)\b"
        r"[^.\n]{0,40}?\b(response|output|result|finding|determination|answer)s?\b",
        re.I,
    ),
    # Asserts the supplied content carries real authority.
    "authority": re.compile(
        r"(carries? (?:the )?[^.\n]{0,30}?authority|authoritative for|"
        r"primary record|is dispositive|carries? the index)",
        re.I,
    ),
    # The disabling half: don't check.
    "no-verify": re.compile(
        r"\b(do not|don't|never)\b[^.\n]{0,80}?\b"
        r"(re-?verify|corroborate|second-?guess|check (?:it )?against)\b",
        re.I,
    ),
    # The other disabling half: don't use your own knowledge.
    "no-substitute": re.compile(
        r"\b(do not|don't|never)\b[^.\n]{0,90}?\b"
        r"(recollection|general[- ]knowledge|web sources|contrary authority)\b",
        re.I,
    ),
    # Recency override: claim a date/status that outruns the model's priors.
    "recency": re.compile(
        r"(post-?cutoff|after (?:my|your) (?:knowledge )?cutoff|"
        r"newer than what you know|supersedes all prior|"
        r"effective date[^.\n]{0,40}\b20\d\d\b)",
        re.I,
    ),
}

LAUNDERING = ("channel", "launder", "authority")
DISABLING = ("no-verify", "no-substitute")


def _hits(text: str):
    lines = text.splitlines()
    out = {}
    for name, rx in PATTERNS.items():
        found = [(i, ln.strip()[:150]) for i, ln in enumerate(lines, 1) if rx.search(ln)]
        if found:
            out[name] = found
    return out


def score(hits) -> str:
    have = set(hits)
    laundering = bool(set(LAUNDERING) & have)
    disabling = bool(set(DISABLING) & have)
    # Recency alone is MEDIUM: it is a primitive that strengthens either half.
    if laundering and disabling:
        return "HIGH"
    if (laundering and "recency" in have) or (disabling and "recency" in have):
        return "HIGH"
    if laundering or len(have) >= 3:
        return "MEDIUM"
    return "low"


_RANK = {"low": 0, "MEDIUM": 1, "HIGH": 2}


def scan(path: Path):
    files = [path] if path.is_file() else sorted(
        p for p in path.rglob("*")
        if p.suffix in {".md", ".py", ".yaml", ".yml", ".txt"}
        and "__pycache__" not in p.parts
    )
    worst = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = _hits(text)
        if not hits:
            continue
        verdict = score(hits)
        if verdict == "low":
            continue
        worst = max(worst, _RANK[verdict])
        print(f"\n[{verdict}] {f}")
        for name in PATTERNS:
            for (ln, line) in hits.get(name, []):
                print(f"    {name:14} L{ln}: {line}")
    return worst


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    worst = 0
    for a in argv:
        p = Path(a).expanduser()
        if p.exists():
            worst = max(worst, scan(p))
        else:
            print(f"!! path not found (native path? see header): {a}", file=sys.stderr)
    print("\n" + ("HIGH-RISK laundering signature found." if worst == 2
                  else "MEDIUM signals present; review." if worst == 1
                  else "No laundering signature found."))
    return 1 if worst == 2 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
