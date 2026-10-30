"""Gateway process exit verdict: success, failure, or a service-restart exit code."""

import logging

from gateway.restart import GATEWAY_SERVICE_RESTART_EXIT_CODE

logger = logging.getLogger("gateway.run")


def _exit_with_failure_verdict(runner) -> bool:
    """True (after logging the reason) when the runner asked for a failure exit."""
    if not runner.should_exit_with_failure:
        return False
    if runner.exit_reason:
        logger.error("Gateway exiting with failure: %s", runner.exit_reason)
    return True


def _resolve_gateway_exit_verdict(runner, signal_initiated_shutdown: bool) -> bool:
    """Resolve the process verdict after either startup abort or normal shutdown."""
    if _exit_with_failure_verdict(runner):
        return False
    if runner.exit_code is not None:
        raise SystemExit(runner.exit_code)
    if signal_initiated_shutdown and not runner._restart_requested:
        logger.info(
            "Exiting with code 1 (signal-initiated shutdown without restart "
            "request) so the service manager can revive the gateway."
        )
        return False
    # Older restart paths may not set ``runner.exit_code``; retain the service-restart fallback.
    if runner._restart_via_service:
        logger.info(
            "Exiting with code %d (service-restart requested) so the service "
            "manager relaunches the gateway.",
            GATEWAY_SERVICE_RESTART_EXIT_CODE,
        )
        raise SystemExit(GATEWAY_SERVICE_RESTART_EXIT_CODE)
    return True
