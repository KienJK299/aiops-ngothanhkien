"""Prometheus metrics for the closed-loop orchestrator."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, start_http_server

action_counter = Counter(
    "closed_loop_actions_total",
    "Total closed-loop actions executed",
    ["service", "runbook", "outcome"],
)

circuit_breaker_gauge = Gauge(
    "closed_loop_circuit_breaker_state",
    "Circuit breaker state per service",
    ["service"],
)

blast_radius_gauge = Gauge(
    "closed_loop_blast_radius_remaining",
    "Remaining actions allowed in the current blast-radius window",
    ["service"],
)

mutex_gauge = Gauge(
    "closed_loop_mutex_locked",
    "Per-service mutex state",
    ["service"],
)

verify_status_gauge = Gauge(
    "closed_loop_verify_status",
    "Last verify result per service+runbook",
    ["service", "runbook"],
)

_started = False


def start_metrics_server(port: int = 9100) -> None:
    global _started
    if _started:
        return
    start_http_server(port)
    _started = True
