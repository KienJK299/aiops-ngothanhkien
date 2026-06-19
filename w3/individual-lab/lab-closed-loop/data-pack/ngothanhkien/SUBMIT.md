# SUBMIT.md - Chaos scenario results

## Scenario 1 - Action succeeds

```json
{"ts":"2026-06-19T07:54:29.835351+00:00","level":"INFO","logger":"orchestrator","event_type":"ALERT_DETECTED","service":"payment-svc","action":"HighLatency","result":"detected","alertname":"HighLatency","severity":"warning"}
{"ts":"2026-06-19T07:54:29.835351+00:00","level":"INFO","logger":"orchestrator","event_type":"DECIDE_RUNBOOK","service":"payment-svc","action":"runbooks/restart_service.sh","result":"matched","alertname":"HighLatency","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:54:29.835351+00:00","level":"INFO","logger":"orchestrator","event_type":"BLAST_RADIUS_OK","service":"payment-svc","action":"runbooks/restart_service.sh","result":"allowed"}
{"ts":"2026-06-19T07:54:29.836350+00:00","level":"INFO","logger":"orchestrator","event_type":"RUNBOOK_EXEC","service":"payment-svc","action":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","result":"dry-run","script":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","dry_run":true}
{"ts":"2026-06-19T07:54:30.066848+00:00","level":"INFO","logger":"orchestrator","event_type":"DRY_RUN_PASS","service":"payment-svc","action":"runbooks/restart_service.sh","result":"pass","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:54:30.068371+00:00","level":"INFO","logger":"orchestrator","event_type":"RUNBOOK_EXEC","service":"payment-svc","action":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","result":"execute","script":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","dry_run":false}
{"ts":"2026-06-19T07:54:32.336590+00:00","level":"INFO","logger":"orchestrator","event_type":"ACTION_EXECUTED","service":"payment-svc","action":"runbooks/restart_service.sh","result":"executed","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:54:32.337160+00:00","level":"INFO","logger":"verify","event_type":"VERIFY_START","service":"payment-svc","action":"HighLatency","result":"running","timeout_s":60}
{"ts":"2026-06-19T07:55:12.469067+00:00","level":"INFO","logger":"orchestrator","event_type":"VERIFY_PASS","service":"payment-svc","action":"runbooks/restart_service.sh","result":"pass","alertname":"HighLatency","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:55:12.470075+00:00","level":"INFO","logger":"orchestrator","event_type":"ACTION_SUCCESS","service":"payment-svc","action":"runbooks/restart_service.sh","result":"success","alertname":"HighLatency","runbook":"runbooks/restart_service.sh"}
```

## Scenario 2 - Action fails -> rollback

```json
{"ts":"2026-06-19T07:59:26.161199+00:00","level":"INFO","logger":"orchestrator","event_type":"ALERT_DETECTED","service":"checkout-svc","action":"InstanceDown","result":"detected","alertname":"InstanceDown","severity":"critical"}
{"ts":"2026-06-19T07:59:26.161199+00:00","level":"INFO","logger":"orchestrator","event_type":"DECIDE_RUNBOOK","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"matched","alertname":"InstanceDown","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:59:26.161199+00:00","level":"INFO","logger":"orchestrator","event_type":"BLAST_RADIUS_OK","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"allowed"}
{"ts":"2026-06-19T07:59:26.163204+00:00","level":"INFO","logger":"orchestrator","event_type":"RUNBOOK_EXEC","service":"checkout-svc","action":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","result":"dry-run","script":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","dry_run":true}
{"ts":"2026-06-19T07:59:26.358393+00:00","level":"INFO","logger":"orchestrator","event_type":"DRY_RUN_PASS","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"pass","runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T07:59:26.359392+00:00","level":"INFO","logger":"orchestrator","event_type":"RUNBOOK_EXEC","service":"checkout-svc","action":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","result":"execute","script":"E:/GP/Xbrain/AIOPS/w3/individual-lab/lab-closed-loop/data-pack/ngothanhkien/runbooks/restart_service.sh","dry_run":false}
{"ts":"2026-06-19T08:00:26.947998+00:00","level":"WARNING","logger":"verify","event_type":"VERIFY_FAIL","service":"checkout-svc","action":"InstanceDown","result":"failed","samples":6}
{"ts":"2026-06-19T08:00:26.947998+00:00","level":"WARNING","logger":"orchestrator","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"triggered","rollback_runbook":"runbooks/restart_service.sh"}
{"ts":"2026-06-19T08:00:29.124472+00:00","level":"INFO","logger":"orchestrator","event_type":"ROLLBACK_EXECUTED","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"completed","rollback_runbook":"runbooks/restart_service.sh"}
```

## Scenario 3 - Circuit breaker

```json
{"ts":"2026-06-19T08:02:50.351514+00:00","level":"INFO","logger":"orchestrator","event_type":"ALERT_DETECTED","service":"checkout-svc","action":"InstanceDown","result":"detected","alertname":"InstanceDown","severity":"critical"}
{"ts":"2026-06-19T08:03:51.458143+00:00","level":"WARNING","logger":"orchestrator","event_type":"ROLLBACK_TRIGGERED","service":"checkout-svc","action":"runbooks/restart_service.sh","result":"triggered","rollback_runbook":"runbooks/restart_service.sh"}
```

