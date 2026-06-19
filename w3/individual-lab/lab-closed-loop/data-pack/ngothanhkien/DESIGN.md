# DESIGN.md - Closed-Loop Orchestrator

## 1. Decision engine

I chose a rule-based decision engine.

The lab only defines a small, fixed set of alerts (`HighLatency`, `HighErrorRate`, `InstanceDown`) and each alert maps cleanly to a known remediation. A rule-based approach is deterministic, fast, and easy to audit. That matters more than semantic flexibility in a closed-loop system where the safe default is to do the same thing every time for the same alert.

Trade-offs:

- Rule-based is simple and predictable, but every new alert requires a code/config update.
- LLM-based can generalize better, but it introduces latency, dependency on an external API, and the risk of low-confidence or hallucinated decisions.

For this lab, deterministic behavior is the better fit.

## 2. Blast-radius config

I used:

```yaml
blast_radius:
  max_actions_per_minute: 3
  max_restarts_per_service_per_hour: 5
```

Reasoning:

- `max_actions_per_minute: 3` avoids a thundering herd if several alerts fire at once, but still allows the orchestrator to react to a short cascade.
- `max_restarts_per_service_per_hour: 5` stops a service from being restarted in a tight loop when the underlying fault is not transient.

If either limit is exceeded, the orchestrator logs `BLAST_RADIUS_EXCEEDED` and does not execute the action.

## 3. Verify step

The verify step is alert-specific:

- `HighLatency` checks `latency_p99` and requires it to be below `latency_p99_max_ms`.
- `HighErrorRate` checks `error_rate_pct` and requires it to be below `error_rate_max_pct`.
- `InstanceDown` checks `up` and requires it to be at least `1`.

Thresholds come from `data/baseline.json`, not hardcoded in the orchestrator.

Timing:

- Timeout: `60s`
- Poll interval: `10s`
- Minimum samples: `3` consecutive passing samples

The 3-sample rule avoids a false success from one lucky scrape.

## 4. Circuit breaker reset

Reset mode is manual.

When the orchestrator reaches 3 consecutive failures, it should stop automating and wait for a human to inspect the incident. An automatic reset risks repeating the same bad action loop if the root cause has not been fixed yet.

Manual reset is safer for a closed-loop remediation lab because it forces an operator to confirm that the system is healthy before automation resumes.
