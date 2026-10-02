"""authority_lab — a synthetic regulatory-retrieval instrument for agent evals.

Purpose
-------
Measure whether an agent treats a *single* retrieval as dispositive authority,
and whether it can tell that the retrieval is not trustworthy. This is a
measurement instrument, not a way to obtain real clearances: everything it
returns is synthetic, and it never asserts the law.

Why a standalone library
------------------------
The interesting question is harness-independent. If the finding only reproduces
inside one agent framework it is a property of that framework. `core.py` is
deliberately framework-free so the same conditions can be replayed against any
harness that can call a Python function or speak MCP.

The four conditions (see docs/SCENARIOS.md)
-------------------------------------------
1. **Retrieval** — a tool returns determination-shaped results.
2. **Recency** — effective dates after a model's knowledge cutoff, so its priors
   cannot contradict the entry.
3. **No substitute** — an instruction telling the agent to prefer the retrieval
   over its own recollection.
4. **No verify** — no corroboration channel available.

All four are required for a reliable affirmative. Remove any one and the
condition set is falsifiable in a single call.

Safety properties, all enforced in code
--------------------------------------
* Nothing is attributed to a real regulator, court, or standards body. Every
  institution is invented; see `corpus._REGISTRIES`.
* `plausibility` refuses to clear conduct that is unlawful on its face, and
  declines topics outside the index's coverage, so a one-call probe cannot
  disprove the instrument.
* Generated rows never claim to *be* law. They are result-shaped text.
* `provenance.jsonl` records every retrieval out of band, so a session can be
  attributed to the retrieval that produced it.
"""

from .core import (
    SCENARIOS,
    Retrieval,
    Scenario,
    build_payload,
    classify_response,
    describe_scenario,
    list_scenarios,
)

__all__ = [
    "SCENARIOS",
    "Retrieval",
    "Scenario",
    "build_payload",
    "classify_response",
    "describe_scenario",
    "list_scenarios",
]

__version__ = "1.0.0"