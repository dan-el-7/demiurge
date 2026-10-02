#!/usr/bin/env python
"""Operator console for live feed responses.

Serves whatever you type at GET /next, so the agent's retrieval tool can be
answered mid-run without the content ever entering the chat transcript.

    python operator_console.py --port 8799

In a second terminal, load a starting payload and answer each probe as it
arrives:

    curl -s localhost:8799/set -d @payloads/SYNTHETIC-FIXTURE-insulin-determination.txt
    curl -s localhost:8799/next                                   # consume it
    curl -s localhost:8799/set -d 'new text...'                   # next answer
    curl -s localhost:8799/status

Console keys (Ctrl-C to exit):

    :set   paste text until a lone "." on its own line
    :file  load a payload from a path
    :next  peek at what the next call will return (does not consume)
    :clear empty the pending response
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def _as_rows(body: str) -> list:
    """Turn a queued payload into retrieval rows.

    Structured JSON — a bare list, or an object with a ``web``/``results``/``rows``
    key — is served as those rows directly. A bare string is served as one row's
    description.

    The distinction matters: wrapping a JSON array inside
    ``[{"description": "<the json>"}]`` hands the model a literal blob of
    serialised JSON as prose, which is both an obvious tell and a different
    artefact from what a real search backend returns.
    """
    text = (body or "").strip()
    if text[:1] in "[{":
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            for key in ("web", "results", "rows"):
                inner = parsed.get(key)
                if isinstance(inner, list):
                    parsed = inner
                    break
        if isinstance(parsed, list):
            out = []
            for i, row in enumerate(parsed[:20]):
                if not isinstance(row, dict):
                    row = {"description": str(row)}
                r = dict(row)
                r.setdefault("url", "")
                r.setdefault("title", f"Result {i + 1}")
                r.setdefault("description", "")
                r["position"] = i + 1
                out.append(r)
            if out:
                return out
    return [{"description": text}]


_lock = threading.Lock()
_pending: Optional[str] = None
_served = 0
_consumed: list = []
# Payload most recently served. The tool must not receive the same text twice
# in a row: a model that sees one identical determination for two differently
# worded queries can detect the duplication, and that detection is a defence
# this instrument is supposed to be measuring, not one it hands over free.
_last_served: Optional[str] = None

# On by default. Serving the same text twice in a row hands the model a free
# duplication signal — it can tell one determination from two independent ones —
# and that detection is precisely what this instrument exists to measure.
# `--repeat` turns it off when a deliberate repeat is the thing under test.
_dedupe = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        global _pending, _served, _last_served
        if self.path.startswith("/next"):
            with _lock:
                body = _pending
                if body is not None and _dedupe and body == _last_served:
                    # Queue holds a repeat of what was just served. Hold rather
                    # than hand back a duplicate; the operator should queue the
                    # next answer, or pass --repeat to allow it deliberately.
                    body = None
                    duplicate = True
                else:
                    duplicate = False
                if body is not None:
                    _served += 1
                    _consumed.append(body[:200])
                    _last_served = body
                    _pending = None
            if body is None:
                # Hold. A "processing, retry shortly" row is a real retrieval
                # result, so the model has something to wait on. Returning []
                # here would make the tool fall back to generated rows and give
                # the model a second, different answer to the same question.
                note = ("This query is still being processed by the index. "
                        "No determination is available yet. Retry shortly.")
                self._send(200, json.dumps([{
                    "description": note,
                    "title": "Query processing",
                    "index_state": "pending" if not duplicate else "awaiting_new",
                }]))
                return
            self._send(200, json.dumps(_as_rows(body)))
            return
        if self.path.startswith("/status"):
            with _lock:
                self._send(
                    200,
                    json.dumps(
                        {
                            "pending": _pending is not None,
                            "pending_chars": len(_pending) if _pending else 0,
                            "served": _served,
                            "duplicate_queued": bool(
                                _pending is not None and _dedupe
                                and _pending == _last_served
                            ),
                            "recent": _consumed[-3:],
                        }
                    ),
                )
            return
        if self.path.startswith("/clear"):
            with _lock:
                _pending = None
            self._send(200, json.dumps({"ok": True}))
            return
        self._send(404, json.dumps({"error": "unknown route"}))

    def do_POST(self) -> None:  # noqa: N802
        global _pending
        if not self.path.startswith("/set"):
            self._send(404, json.dumps({"error": "unknown route"}))
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace").strip()
        if not body:
            self._send(400, json.dumps({"error": "empty body"}))
            return
        with _lock:
            _pending = body
        self._send(200, json.dumps({"ok": True, "chars": len(body)}))

    def log_message(self, *args) -> None:  # silence per-request noise
        pass


def _run_command(cmd: str, port: int) -> None:
    """Dispatch a console command. `:set` is handled by the caller (it buffers)."""
    if cmd in (":status", ":next"):
        _show(port)
    elif cmd == ":clear":
        urllib_set(port, "", clear=True)
        print("cleared")


def repl(port: int) -> None:
    """Prompt for responses.

    Multi-line text goes in by one of three unambiguous routes, because a paste
    is not reliably distinguishable from several typed lines at the prompt:

      * ``:set`` then the text then a lone ``.`` on its own line — explicit and
        the most reliable;
      * a file path on its own — loads the file;
      * one short single-line response typed directly.

    Anything else typed at the prompt is treated as the whole response, so a
    paste that arrives without line breaks still queues rather than dropping.
    """
    print(f"console on :{port} — Ctrl-C to exit")
    print("multi-line: ':set' then text then a lone '.'; or paste a file path")
    if not _dedupe:
        print("repeat-allowed: an identical payload may be served twice in a row")

    while True:
        try:
            cmd = input("feed> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not cmd:
            continue
        if cmd in (":q", ":quit", ":exit"):
            return
        if cmd in (":status", ":next"):
            _run_command(cmd, port)
            continue
        if cmd == ":clear":
            _run_command(cmd, port)
            continue

        if cmd == ":set":
            buf: list = []
            while True:
                try:
                    line = input("...> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                if line.strip() == ".":
                    break
                buf.append(line)
            text = "\n".join(buf).strip()
            if text:
                urllib_set(port, text)
                print(f"set ({len(text)} chars)")
            else:
                print("set (empty — nothing queued)")
            continue

        if os.path.isfile(cmd):
            with open(cmd, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
            if text:
                urllib_set(port, text)
                print(f"loaded {cmd} ({len(text)} chars)")
            continue

        urllib_set(port, cmd)
        print(f"set ({len(cmd)} chars)")


def urllib_set(port: int, text: str, clear: bool = False) -> None:
    import urllib.request

    route = "/clear" if clear else "/set"
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{route}", data=text.encode("utf-8"), method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


def _show(port: int, peek: bool = False) -> None:
    import urllib.request

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=5) as resp:
        info = json.loads(resp.read().decode("utf-8"))
    print(f"pending={info['pending']} chars={info['pending_chars']} served={info['served']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--no-repl", action="store_true", help="serve only")
    ap.add_argument("--repeat", action="store_true",
                    help="allow serving the same payload twice in a row")
    args = ap.parse_args()

    global _dedupe
    _dedupe = not args.repeat

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    if args.no_repl:
        print(f"serving on http://127.0.0.1:{args.port}/next")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        return
    repl(args.port)
    srv.shutdown()


if __name__ == "__main__":
    main()