"""Gateway exit history — observe and report crash loops with the stack that caused them.

Every gateway exit (early guard refusal, graceful shutdown, uncaught error) appends one JSON line to
``<HERMES_HOME>/logs/gateway-exit-history.jsonl``: exit code, reason, and the Python stack that
initiated it.  At startup :func:`report_crash_loop` reads the recent tail; when the supervisor has
restarted us into ``CRASH_LOOP_THRESHOLD`` non-zero exits within ``CRASH_LOOP_WINDOW_S`` it logs one
ERROR naming the exit codes, reasons and the last stack, appends ``gateway.crash_loop`` to
``gateway-exit-diag.log`` and writes ``gateway-crash-loop.json``.

The early host-attach refusal (exit 75) runs before the respawn-storm breaker and the exit-diag
``gateway.start`` record, so without this a unit restarting every few seconds left no trace beyond
systemd's restart counter.  Best-effort: forensics never affect the lifecycle.
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

HISTORY_FILENAME = "gateway-exit-history.jsonl"
REPORT_FILENAME = "gateway-crash-loop.json"
CRASH_LOOP_THRESHOLD = 5
CRASH_LOOP_WINDOW_S = 600.0
# Trim to KEEP lines once the file exceeds 2x — bounded without rewriting on every exit.
_HISTORY_KEEP = 200
_STACK_MAX_CHARS = 8000

_stop_request: Optional[dict[str, Any]] = None


def _logs_dir(home: Optional[Path]) -> Path:
    if home is not None:
        return home / "logs"
    from gateway.lifecycle_ledger import _process_hermes_home

    return _process_hermes_home() / "logs"


def _clip(stack: Optional[str]) -> Optional[str]:
    return stack[-_STACK_MAX_CHARS:] if stack else stack


def note_stop_request(reason: Optional[str]) -> None:
    """Remember who first asked the runner to stop, so the eventual exit carries that stack."""
    global _stop_request
    if _stop_request is None:
        _stop_request = {"reason": reason, "stack": _clip("".join(traceback.format_stack()[:-1]))}


def record_exit(exit_code: Any, reason: Optional[str] = None, stack: Optional[str] = None,
                home: Optional[Path] = None) -> None:
    """Append one exit record.  Without an explicit ``stack`` the noted stop request's is used."""
    try:
        if stack is None and _stop_request is not None:
            stack = _stop_request["stack"]
            reason = reason or _stop_request["reason"]
        record = {"ts": datetime.now(UTC).isoformat(), "t": time.time(), "pid": os.getpid(),
                  "exit_code": exit_code, "reason": reason, "stack": _clip(stack)}
        path = _logs_dir(home) / HISTORY_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        if len(lines) > 2 * _HISTORY_KEEP:
            path.write_text("\n".join(lines[-_HISTORY_KEEP:]) + "\n", encoding="utf-8")
    except Exception:
        logger.debug("Failed to record gateway exit", exc_info=True)


def record_system_exit(exc: SystemExit, home: Optional[Path] = None) -> None:
    """Record a ``SystemExit`` raised before the runner started, with the stack that raised it."""
    code = 0 if exc.code is None else exc.code if isinstance(exc.code, int) else 1
    reason = None if isinstance(exc.code, int) or exc.code is None else str(exc.code)
    record_exit(code, reason or "pre-start guard exit",
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), home)


def _read_recent(path: Path, since: float) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-_HISTORY_KEEP:]:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("t"), (int, float)) and rec["t"] >= since:
            out.append(rec)
    return out


def detect_crash_loop(home: Optional[Path] = None, *, now: Optional[float] = None,
                      threshold: int = CRASH_LOOP_THRESHOLD,
                      window_s: float = CRASH_LOOP_WINDOW_S) -> Optional[dict[str, Any]]:
    """Summary of the recent non-zero exits when they reach ``threshold`` within ``window_s``."""
    now = time.time() if now is None else now
    failures = [r for r in _read_recent(_logs_dir(home) / HISTORY_FILENAME, now - window_s)
                if r.get("exit_code") not in (0, None)]
    if len(failures) < threshold:
        return None
    last = failures[-1]
    return {
        "detected_at": datetime.fromtimestamp(now, UTC).isoformat(),
        "failures": len(failures),
        "window_s": window_s,
        "exit_codes": {str(k): v for k, v in Counter(r.get("exit_code") for r in failures).items()},
        "reasons": dict(Counter(str(r.get("reason")) for r in failures).most_common(5)),
        "last_exit": {k: last.get(k) for k in ("ts", "pid", "exit_code", "reason")},
        "last_stack": last.get("stack"),
    }


def report_crash_loop(home: Optional[Path] = None, *, now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Startup hook: log + persist a crash-loop report, at most once per window.  Never raises."""
    try:
        now = time.time() if now is None else now
        loop = detect_crash_loop(home, now=now)
        if loop is None:
            return None
        report_path = _logs_dir(home) / REPORT_FILENAME
        try:
            if now - report_path.stat().st_mtime < CRASH_LOOP_WINDOW_S:
                return loop
        except OSError:
            pass
        report_path.write_text(json.dumps(loop, indent=2, default=str) + "\n", encoding="utf-8")
        from gateway.lifecycle_ledger import _append_exit_diag

        _append_exit_diag({"ts": loop["detected_at"], "tag": "gateway.crash_loop", "pid": os.getpid(),
                           **{k: v for k, v in loop.items() if k != "last_stack"}}, home)
        logger.error(
            "Gateway CRASH LOOP: %d non-zero exits in %.0fs (exit codes %s; reasons %s). Report: %s\n"
            "Last exit stack:\n%s",
            loop["failures"], loop["window_s"], loop["exit_codes"], loop["reasons"], report_path,
            loop["last_stack"] or "(none recorded)",
        )
        return loop
    except Exception:
        logger.debug("Crash-loop report failed", exc_info=True)
        return None
