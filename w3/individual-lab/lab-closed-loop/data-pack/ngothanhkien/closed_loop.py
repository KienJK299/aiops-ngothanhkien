#!/usr/bin/env python3
"""Ronki closed-loop auto-remediation orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import requests
import yaml

from engine.logger import JsonLogger
from engine.metrics import (
    action_counter,
    blast_radius_gauge,
    circuit_breaker_gauge,
    mutex_gauge,
    start_metrics_server,
    verify_status_gauge,
)
from engine.safety import BlastRadiusGuard, CircuitBreaker
from engine.verify import verify_service

log = JsonLogger("orchestrator")
_service_locks: dict[str, threading.Lock] = {}
_service_locks_guard = threading.Lock()


def get_service_lock(service: str) -> threading.Lock:
    with _service_locks_guard:
        lock = _service_locks.get(service)
        if lock is None:
            lock = threading.Lock()
            _service_locks[service] = lock
        return lock


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fetch_active_alerts(alertmanager_url: str) -> list[dict[str, Any]]:
    try:
        response = requests.get(f"{alertmanager_url}/api/v2/alerts", timeout=5)
        response.raise_for_status()
        alerts = response.json()
        return [alert for alert in alerts if alert.get("status", {}).get("state", "active") == "active"]
    except Exception as exc:  # pragma: no cover - network failure path
        log.error("ALERTMANAGER_FETCH_ERROR", service="", action="poll_alertmanager", result="error", error=str(exc))
        return []


def extract_service(alert: dict[str, Any]) -> str:
    labels = alert.get("labels", {})
    return labels.get("service") or labels.get("job") or "unknown"


def resolve_path(base_dir: Path, relative_path: str) -> Path:
    return (base_dir / relative_path).resolve()


def to_bash_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return resolved.as_posix()

    as_posix = resolved.as_posix()
    if ":/" not in as_posix:
        return as_posix

    drive, rest = as_posix.split(":/", 1)
    return f"/mnt/{drive.lower()}/{rest}"


def validate_runbook(runbook: str, cfg: dict[str, Any], alertname: str) -> bool:
    registry = list(cfg.get("runbook_registry", cfg.get("runbook_map", {}).values()))
    if runbook in registry:
        return True
    log.error(
        "DECISION_VALIDATION_FAILED",
        service="",
        action=runbook,
        result="escalate_no_auto_action",
        bad_runbook=runbook,
        alertname=alertname,
        raw_decision=runbook,
    )
    return False


def run_runbook(script_path: Path, service: str, dry_run: bool, timeout_s: int) -> bool:
    bash_script_path = to_bash_path(script_path)
    command = ["bash", bash_script_path, "--service", service]
    if dry_run:
        command.append("--dry-run")

    log.info(
        "RUNBOOK_EXEC",
        service=service,
        action=script_path.as_posix(),
        result="dry-run" if dry_run else "execute",
        script=script_path.as_posix(),
        dry_run=dry_run,
    )
    import subprocess

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        log.info(
            "RUNBOOK_RESULT",
            service=service,
            action=script_path.as_posix(),
            result="success" if result.returncode == 0 else "failure",
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log.error(
            "RUNBOOK_TIMEOUT",
            service=service,
            action=script_path.as_posix(),
            result="timeout",
            timeout_s=timeout_s,
        )
        return False
    except Exception as exc:  # pragma: no cover - subprocess failure path
        log.error(
            "RUNBOOK_ERROR",
            service=service,
            action=script_path.as_posix(),
            result="error",
            error=str(exc),
        )
        return False


def run_transactional_steps(steps: list[str], service: str, cfg_dir: Path, timeout_s: int) -> tuple[bool, list[str]]:
    completed_steps: list[str] = []
    for step in steps:
        step_path = resolve_path(cfg_dir, step)
        if not run_runbook(step_path, service, dry_run=False, timeout_s=timeout_s):
            log.error(
                "TRANSACTIONAL_STEP_FAIL",
                service=service,
                action=step_path.as_posix(),
                result="failed",
                completed_before_failure=completed_steps,
                step=step,
            )
            return False, completed_steps
        completed_steps.append(step)
        log.info(
            "TRANSACTIONAL_STEP",
            service=service,
            action=step_path.as_posix(),
            result="success",
            step=step,
        )
    return True, completed_steps


def process_alert(
    alert: dict[str, Any],
    cfg: dict[str, Any],
    baseline: dict[str, Any],
    guard: BlastRadiusGuard,
    cb: CircuitBreaker,
    config_dir: Path,
    global_dry_run: bool,
) -> None:
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "")
    service = extract_service(alert)
    severity = labels.get("severity", "")

    log.info(
        "ALERT_DETECTED",
        service=service,
        action=alertname,
        result="detected",
        alertname=alertname,
        severity=severity,
    )

    runbook = cfg.get("runbook_map", {}).get(alertname)
    if not runbook:
        log.warning(
            "NO_RUNBOOK",
            service=service,
            action=alertname,
            result="ignored",
            alertname=alertname,
        )
        return

    if not validate_runbook(runbook, cfg, alertname):
        return

    log.info(
        "DECIDE_RUNBOOK",
        service=service,
        action=runbook,
        result="matched",
        alertname=alertname,
        runbook=runbook,
    )

    allowed, reason = guard.check(service)
    if not allowed:
        log.warning(
            "BLAST_RADIUS_EXCEEDED",
            service=service,
            action=runbook,
            result="blocked",
            reason=reason,
        )
        return

    log.info("BLAST_RADIUS_OK", service=service, action=runbook, result="allowed")
    blast_radius_gauge.labels(service=service).set(guard.remaining(service))

    service_lock = get_service_lock(service)
    if not service_lock.acquire(blocking=False):
        log.warning(
            "SERVICE_LOCK_BUSY",
            service=service,
            action=runbook,
            result="skipped",
            message="another runbook is already executing for this service",
        )
        return

    mutex_gauge.labels(service=service).set(1)
    circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
    try:
        timeout_s = int(cfg.get("runbook_timeout_seconds", 30))
        baseline_thresholds = baseline["verify_thresholds"]
        verify_policy = cfg.get("verify_policy", {})
        policy = verify_policy.get(alertname, {"metric": "latency_p99", "threshold": "latency_p99_max_ms", "comparison": "lt"})

        runbook_path = resolve_path(config_dir, runbook)
        if not run_runbook(runbook_path, service, dry_run=True, timeout_s=timeout_s):
            log.error(
                "DRY_RUN_FAIL",
                service=service,
                action=runbook,
                result="failed",
                runbook=runbook,
            )
            action_counter.labels(service=service, runbook=runbook, outcome="fail").inc()
            cb.record_failure()
            circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
            return

        log.info("DRY_RUN_PASS", service=service, action=runbook, result="pass", runbook=runbook)

        if global_dry_run:
            action_counter.labels(service=service, runbook=runbook, outcome="dry_run").inc()
            log.info("GLOBAL_DRY_RUN_SKIP", service=service, action=runbook, result="skipped")
            return

        if alertname in cfg.get("multi_step_map", {}):
            steps = cfg["multi_step_map"][alertname]
            ok, completed = run_transactional_steps(steps, service, config_dir, timeout_s)
            if not ok:
                rollback_steps = cfg.get("multi_step_rollback_map", {}).get(alertname, [])
                for rollback_step in reversed(rollback_steps[: len(completed)]):
                    rollback_path = resolve_path(config_dir, rollback_step)
                    log.warning(
                        "TRANSACTIONAL_ROLLBACK_STEP",
                        service=service,
                        action=rollback_path.as_posix(),
                        result="rollback",
                        step=rollback_step,
                    )
                    run_runbook(rollback_path, service, dry_run=False, timeout_s=timeout_s)
                log.info(
                    "TRANSACTIONAL_ROLLBACK_COMPLETE",
                    service=service,
                    action=runbook,
                    result="rolled_back",
                    rolled_back=list(reversed(rollback_steps[: len(completed)])),
                )
                cb.record_failure()
                circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
                action_counter.labels(service=service, runbook=runbook, outcome="rollback").inc()
                return
        else:
            if not run_runbook(runbook_path, service, dry_run=False, timeout_s=timeout_s):
                log.error("ACTION_EXEC_FAIL", service=service, action=runbook, result="failed", runbook=runbook)
                action_counter.labels(service=service, runbook=runbook, outcome="fail").inc()
                cb.record_failure()
                circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
                return

        log.info("ACTION_EXECUTED", service=service, action=runbook, result="executed", runbook=runbook)

        verify_status_gauge.labels(service=service, runbook=runbook).set(2)
        verify_ok = verify_service(
            prometheus_url=str(cfg["prometheus_url"]),
            service=service,
            alertname=alertname,
            baseline=baseline,
            metric_policy=policy,
            timeout_s=int(baseline_thresholds["verify_timeout_seconds"]),
            poll_interval_s=int(baseline_thresholds["verify_poll_interval_seconds"]),
            min_samples=int(baseline_thresholds["verify_min_samples"]),
        )

        if verify_ok:
            verify_status_gauge.labels(service=service, runbook=runbook).set(1)
            action_counter.labels(service=service, runbook=runbook, outcome="success").inc()
            log.info("VERIFY_PASS", service=service, action=runbook, result="pass", alertname=alertname, runbook=runbook)
            log.info("ACTION_SUCCESS", service=service, action=runbook, result="success", alertname=alertname, runbook=runbook)
            cb.record_success()
            circuit_breaker_gauge.labels(service=service).set(0)
            return

        verify_status_gauge.labels(service=service, runbook=runbook).set(0)
        log.warning("VERIFY_FAIL", service=service, action=runbook, result="failed", alertname=alertname, runbook=runbook)
        action_counter.labels(service=service, runbook=runbook, outcome="rollback").inc()
        rollback_runbook = cfg.get("rollback_map", {}).get(alertname, runbook)
        rollback_path = resolve_path(config_dir, rollback_runbook)
        log.warning(
            "ROLLBACK_TRIGGERED",
            service=service,
            action=rollback_runbook,
            result="triggered",
            rollback_runbook=rollback_runbook,
        )
        run_runbook(rollback_path, service, dry_run=False, timeout_s=timeout_s)
        log.info(
            "ROLLBACK_EXECUTED",
            service=service,
            action=rollback_runbook,
            result="completed",
            rollback_runbook=rollback_runbook,
        )
        cb.record_failure()
        circuit_breaker_gauge.labels(service=service).set(1 if cb.is_open() else 0)
    finally:
        mutex_gauge.labels(service=service).set(0)
        service_lock.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ronki closed-loop orchestrator")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="log-only mode; do not execute real actions")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config_dir = config_path.parent
    cfg = load_config(config_path)
    baseline = load_json(resolve_path(config_dir, cfg["baseline_path"]))

    guard = BlastRadiusGuard(
        max_per_minute=int(cfg["blast_radius"]["max_actions_per_minute"]),
        max_restarts_per_hour=int(cfg["blast_radius"]["max_restarts_per_service_per_hour"]),
    )
    cb = CircuitBreaker(threshold=int(cfg["circuit_breaker"]["consecutive_failure_threshold"]))
    seen: set[str] = set()

    start_metrics_server()
    log.info("ORCHESTRATOR_START", service="", action="startup", result="running", config=str(config_path), dry_run=args.dry_run)

    poll_interval = int(cfg.get("poll_interval_seconds", 15))
    while True:
        if cb.is_open():
            log.error("CIRCUIT_BREAKER_HALT", service="", action="poll", result="halted", message="Circuit open; polling suspended.")
            time.sleep(poll_interval)
            continue

        alerts = fetch_active_alerts(str(cfg["alertmanager_url"]))
        seen_cycle: set[str] = set()
        new_alerts: list[dict[str, Any]] = []
        for alert in alerts:
            fingerprint = alert.get("fingerprint", "")
            if fingerprint and fingerprint in seen_cycle:
                continue
            if fingerprint:
                seen_cycle.add(fingerprint)
            new_alerts.append(alert)

        if new_alerts:
            max_workers = min(8, len(new_alerts))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(process_alert, alert, cfg, baseline, guard, cb, config_dir, args.dry_run)
                    for alert in new_alerts
                ]
                wait(futures)

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
