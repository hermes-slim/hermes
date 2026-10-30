"""Gateway exit history: a supervisor restart loop is observed, reported, and carries its stack."""

import json
import logging

import pytest

from gateway import exit_history


@pytest.fixture(autouse=True)
def _fresh_stop_request(monkeypatch):
    monkeypatch.setattr(exit_history, "_stop_request", None)


def _refuse_attach():
    raise SystemExit(75)


def _exit_via_guard(home):
    try:
        _refuse_attach()
    except SystemExit as exc:
        exit_history.record_system_exit(exc, home=home)


def test_repeated_guard_exits_report_a_crash_loop_with_the_raising_stack(tmp_path, caplog):
    for _ in range(exit_history.CRASH_LOOP_THRESHOLD):
        _exit_via_guard(tmp_path)

    with caplog.at_level(logging.ERROR, logger="gateway.exit_history"):
        loop = exit_history.report_crash_loop(tmp_path)

    assert loop["failures"] == exit_history.CRASH_LOOP_THRESHOLD
    assert loop["exit_codes"] == {"75": exit_history.CRASH_LOOP_THRESHOLD}
    assert "_refuse_attach" in loop["last_stack"]
    assert "CRASH LOOP" in caplog.text and "_refuse_attach" in caplog.text
    report = json.loads((tmp_path / "logs" / exit_history.REPORT_FILENAME).read_text())
    assert report["failures"] == exit_history.CRASH_LOOP_THRESHOLD
    diag = (tmp_path / "logs" / "gateway-exit-diag.log").read_text()
    assert '"tag": "gateway.crash_loop"' in diag


def test_clean_exits_and_old_failures_are_not_a_loop(tmp_path):
    for _ in range(10):
        exit_history.record_exit(0, home=tmp_path)
    assert exit_history.report_crash_loop(tmp_path) is None

    for _ in range(exit_history.CRASH_LOOP_THRESHOLD):
        exit_history.record_exit(1, "boom", home=tmp_path)
    later = exit_history.time.time() + exit_history.CRASH_LOOP_WINDOW_S + 1
    assert exit_history.detect_crash_loop(tmp_path, now=later) is None


def test_report_is_logged_once_per_window(tmp_path, caplog):
    for _ in range(exit_history.CRASH_LOOP_THRESHOLD):
        exit_history.record_exit(75, home=tmp_path)
    with caplog.at_level(logging.ERROR, logger="gateway.exit_history"):
        exit_history.report_crash_loop(tmp_path)
        exit_history.report_crash_loop(tmp_path)
    assert caplog.text.count("CRASH LOOP") == 1


def test_exit_after_a_stop_request_carries_the_requesting_stack(tmp_path):
    def adapters_all_disconnected():
        exit_history.note_stop_request("All messaging adapters disconnected")

    adapters_all_disconnected()
    exit_history.record_exit(1, home=tmp_path)

    rec = json.loads((tmp_path / "logs" / exit_history.HISTORY_FILENAME).read_text().splitlines()[-1])
    assert rec["exit_code"] == 1
    assert rec["reason"] == "All messaging adapters disconnected"
    assert "adapters_all_disconnected" in rec["stack"]


def test_run_gateway_records_the_host_attach_refusal(tmp_path, monkeypatch):
    from hermes_cli import gateway as gateway_cli

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(gateway_cli, "_guard_official_docker_root_gateway", lambda: None)

    def attach_refuses(**_kwargs):
        raise SystemExit(75)

    monkeypatch.setattr(gateway_cli, "_attach_to_host_gateway_or_guard", attach_refuses)

    with pytest.raises(SystemExit):
        gateway_cli.run_gateway()

    rec = json.loads((tmp_path / "logs" / exit_history.HISTORY_FILENAME).read_text().splitlines()[-1])
    assert rec["exit_code"] == 75
    assert "attach_refuses" in rec["stack"]
