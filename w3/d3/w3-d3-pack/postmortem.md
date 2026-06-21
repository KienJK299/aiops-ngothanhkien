# Postmortem: Cloudflare Regex Catastrophic Backtracking (2026-06-21)

## Summary
The API Gateway experienced a total resource exhaustion (100% CPU) due to a catastrophic backtracking event in a regex-based WAF middleware. This caused cascading latency and request drops across payment and inventory services, lasting 12 minutes until manual service restart.

## Impact
- **Users affected:** 100% of concurrent API users.
- **Services affected:** `cloudflare_regex_2019-api-1`, `payment-svc`, `inventory-svc`.
- **Duration:** 2026-06-21 19:00 UTC → 19:12 UTC (12 minutes).

## Timeline (UTC)
| UTC | Event |
|:---|:---|
| 2026-06-21 19:00 | Container startup |
| 2026-06-21 19:05 | Pipeline alert: WAF_Rule_Active |
| 2026-06-21 19:06 | Prometheus alert: ContainerCPUExhausted firing |
| 2026-06-21 19:08 | HTTP_Gateway_Timeout firing |
| 2026-06-21 19:09 | Pipeline alert: Latency_Anomaly on payment-svc |
| 2026-06-21 19:10 | Http_Requests_Slow firing |
| 2026-06-21 19:12 | Manual container restart |
| 2026-06-21 19:12 | ContainerCPUExhausted resolved |

## Root cause
The application utilized an unoptimized regex pattern in a middleware component, which triggered a catastrophic backtracking loop when processing specially crafted input payloads.

## Contributing factors
1. Lack of input validation/length limits on the query parameters.
2. Synchronous processing model causing head-of-line blocking for downstream services.

## Detection
- **Detection method:** Automated AIOps Pipeline & Prometheus Alerts.
- **MTTD:** ~90 seconds.
- **Pipeline gaps:** - Scrape interval (15s) introduced artificial delay in alert firing.
  - Absence of auto-healing triggers resulted in unnecessary manual intervention.

## Response
- **Action:** Manual identification and restart of the affected container.
- **Mitigation:** 12 minutes.

## Action items
| # | Action | Owner | Type | ETA |
|:---|:---|:---|:---|:---|
| 1 | Refactor regex patterns | SRE Team | preventive | 2026-06-22 |
| 2 | Enforce input length constraints | Dev Team | preventive | 2026-06-23 |
| 3 | Implement liveness probes | DevOps | detective | 2026-06-24 |