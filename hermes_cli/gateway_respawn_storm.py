"""Portable app-level respawn-storm breaker for ``hermes gateway run``."""

import logging
import os
import time

logger = logging.getLogger("hermes_cli.gateway")


def respawn_storm_backoff() -> None:
    """Portable app-level respawn-storm breaker (for supervisors without a floor). Defaults mirror
    DEFAULT_CONFIG ``gateway.respawn_storm``; HERMES_GATEWAY_MAX_STARTS / HERMES_GATEWAY_START_WINDOW_S
    override; max_starts <= 0 disables. Never blocks startup."""
    try:
        from gateway.status import record_start_and_check_storm
        _max_starts = 5
        _win = 120.0
        try:
            from hermes_cli.config import load_config
            _cfg = load_config()
            _gw = _cfg.get("gateway") if isinstance(_cfg, dict) else None
            _rs = _gw.get("respawn_storm") if isinstance(_gw, dict) else None
            if isinstance(_rs, dict):
                if isinstance(_rs.get("max_starts"), int):
                    _max_starts = _rs["max_starts"]
                if isinstance(_rs.get("window_seconds"), (int, float)):
                    _win = float(_rs["window_seconds"])
        except Exception:
            pass
        try:
            _max_starts = int(os.environ["HERMES_GATEWAY_MAX_STARTS"])
        except (KeyError, ValueError):
            pass
        try:
            _win = float(os.environ["HERMES_GATEWAY_START_WINDOW_S"])
        except (KeyError, ValueError):
            pass
        _storm = record_start_and_check_storm(max_starts=_max_starts, window_s=_win) if _max_starts > 0 else None
        if _storm is not None:
            logger.warning(
                "Gateway (re)started %d times in %.0fs — backing off %.0fs to break a respawn storm.",
                _storm.count, _storm.window_s, _storm.backoff_s,
            )
            # Tell the startup watchdog the backoff sleep is intentional, not a parked deadlock.
            try:
                from hermes_startup_watchdog import kick_startup_watchdog
                kick_startup_watchdog(extra_s=_storm.backoff_s)
            except Exception:
                pass
            time.sleep(_storm.backoff_s)
    except Exception as _be:
        logger.debug("respawn-storm breaker check failed (non-fatal): %s", _be)
