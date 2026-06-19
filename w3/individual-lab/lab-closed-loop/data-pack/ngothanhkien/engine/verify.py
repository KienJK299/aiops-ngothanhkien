"""Prometheus-based verify step for the closed-loop orchestrator."""

from __future__ import annotations

import time
from typing import Any

import requests

from engine.logger import JsonLogger

log = JsonLogger("verify")


def query_prometheus(prometheus_url: str, promql: str) -> float | None:
    try:
        response = requests.get(f"{prometheus_url}/api/v1/query", params={"query": promql}, timeout=5)
        response.raise_for_status()
        results = response.json().get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
    except Exception as exc:  # pragma: no cover - network failure path
        log.error("PROMETHEUS_QUERY_ERROR", service="", action=promql, result="error", query=promql, error=str(exc))
    return None


def verify_service(
    prometheus_url: str,
    service: str,
    alertname: str,
    baseline: dict[str, Any],
    metric_policy: dict[str, Any],
    timeout_s: int,
    poll_interval_s: int,
    min_samples: int,
) -> bool:
    thresholds = baseline["verify_thresholds"]
    queries = baseline["prometheus_queries"]
    metric_name = metric_policy["metric"]
    threshold_key = metric_policy["threshold"]
    comparison = metric_policy["comparison"]

    query_template = queries[metric_name]
    if metric_name == "latency_p99":
        promql = query_template.replace("{service}", service)
    else:
        promql = query_template.replace("{service}", service)

    deadline = time.time() + timeout_s
    passes = 0
    samples = 0

    log.info("VERIFY_START", service=service, action=alertname, result="running", timeout_s=timeout_s)

    while time.time() < deadline:
        metric_value = query_prometheus(prometheus_url, promql)
        samples += 1
        threshold_value = thresholds[threshold_key]

        if comparison == "lt":
            metric_ok = metric_value is not None and metric_value < threshold_value
        else:
            metric_ok = metric_value is not None and metric_value >= threshold_value

        log.info(
            "VERIFY_SAMPLE",
            service=service,
            action=alertname,
            result="sampled",
            sample=samples,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold_value,
            metric_ok=metric_ok,
        )

        if metric_ok:
            passes += 1
            if passes >= min_samples:
                log.info("VERIFY_PASS", service=service, action=alertname, result="pass", samples=samples)
                return True
        else:
            passes = 0

        time.sleep(poll_interval_s)

    log.warning("VERIFY_FAIL", service=service, action=alertname, result="failed", samples=samples)
    return False
