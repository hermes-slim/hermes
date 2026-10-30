"""Fail-closed guard for an unparseable profile config.yaml at gateway start."""

import sys


def guard_corrupt_user_config() -> None:
    """Fail closed when the active profile's config.yaml cannot be parsed: nobody can repair it on this
    surface, and defaults would let provider auto-detection adopt ``.env`` credentials the config never
    named. Same policy and escape hatch (``HERMES_IGNORE_USER_CONFIG=1``) as ``hermes_cli/main.py``."""
    from hermes_cli.config import InvalidUserConfigError, require_parseable_user_config

    try:
        require_parseable_user_config()
    except InvalidUserConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
