from fastapi import FastAPI, Request
import json
import uvicorn
from collections import deque
from datetime import datetime

app = FastAPI()
ALERTS_FILE = "alerts.jsonl"

# =========================
# CONFIG
# =========================
WINDOW = 10
PERSISTENCE = 3
ALPHA = 0.3  # EWMA smoothing

# =========================
# STATE
# =========================
timeout_history = deque(maxlen=WINDOW)
error_history = deque(maxlen=WINDOW)
rps_history = deque(maxlen=WINDOW)
latency_history = deque(maxlen=WINDOW)

ewma_timeout = None
ewma_error = None
ewma_rps = None

incident_state = {
    "dependency_timeout": False,
    "traffic_spike": False,
    "memory_leak": False
}

def save_alert(alert):
    with open(ALERTS_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")

def now_iso():
    return datetime.utcnow().isoformat()

def update_ewma(prev, value):
    if prev is None:
        return value
    return ALPHA * value + (1 - ALPHA) * prev


# =========================
# MAIN ENDPOINT
# =========================
@app.post("/ingest")
async def ingest(request: Request):
    global ewma_timeout, ewma_error, ewma_rps

    payload = await request.json()
    metrics = payload["metrics"]
    logs = payload["logs"]

    mem = metrics["memory_usage_bytes"]
    mem_limit = metrics["memory_limit_bytes"]
    rps = metrics["http_requests_per_sec"]
    latency = metrics["http_p99_latency_ms"]
    error_rate = metrics["http_5xx_rate"]
    timeout_rate = metrics["upstream_timeout_rate"]

    # =========================
    # UPDATE HISTORY
    # =========================
    timeout_history.append(timeout_rate)
    error_history.append(error_rate)
    rps_history.append(rps)
    latency_history.append(latency)

    # =========================
    # UPDATE EWMA
    # =========================
    ewma_timeout = update_ewma(ewma_timeout, timeout_rate)
    ewma_error = update_ewma(ewma_error, error_rate)
    ewma_rps = update_ewma(ewma_rps, rps)

    # =========================
    # 1. DEPENDENCY TIMEOUT
    # =========================
    if len(timeout_history) == WINDOW:
        persist_timeout = all(t > 0.3 for t in list(timeout_history)[-PERSISTENCE:])
        persist_error = all(e > 0.5 for e in list(error_history)[-PERSISTENCE:])

        is_anomaly = (
            ewma_timeout > 0.3 and
            ewma_error > 0.5 and
            persist_timeout and
            persist_error
        )

        if is_anomaly and not incident_state["dependency_timeout"]:
            incident_state["dependency_timeout"] = True

            save_alert({
                "timestamp": now_iso(),
                "type": "dependency_timeout",
                "severity": "critical",
                "message": f"EWMA timeout={ewma_timeout:.2f}, error={ewma_error:.2f}"
            })

        elif not is_anomaly and incident_state["dependency_timeout"]:
            incident_state["dependency_timeout"] = False

            save_alert({
                "timestamp": now_iso(),
                "type": "dependency_timeout",
                "severity": "warning",
                "message": "Recovered from dependency timeout"
            })

    # =========================
    # 2. TRAFFIC SPIKE
    # =========================
    if len(rps_history) == WINDOW:
        avg_rps = sum(rps_history) / WINDOW

        persist_rps = all(r > avg_rps * 1.5 for r in list(rps_history)[-PERSISTENCE:])
        persist_latency = all(l > 100 for l in list(latency_history)[-PERSISTENCE:])

        is_spike = persist_rps and persist_latency

        if is_spike and not incident_state["traffic_spike"]:
            incident_state["traffic_spike"] = True

            save_alert({
                "timestamp": now_iso(),
                "type": "traffic_spike",
                "severity": "warning",
                "message": f"RPS spike sustained, avg={avg_rps:.1f}"
            })

        elif not is_spike and incident_state["traffic_spike"]:
            incident_state["traffic_spike"] = False

            save_alert({
                "timestamp": now_iso(),
                "type": "traffic_spike",
                "severity": "warning",
                "message": "Traffic returned to normal"
            })

    # =========================
    # 3. MEMORY LEAK
    # =========================
    utilization = mem / mem_limit

    if len(timeout_history) == WINDOW:
        # detect increasing trend
        trend_up = all(
            x < y for x, y in zip(timeout_history, list(timeout_history)[1:])
        )

        is_leak = utilization > 0.8 and trend_up

        if is_leak and not incident_state["memory_leak"]:
            incident_state["memory_leak"] = True

            save_alert({
                "timestamp": now_iso(),
                "type": "memory_leak",
                "severity": "critical",
                "message": f"Memory leak suspected, utilization={utilization:.2f}"
            })

        elif not is_leak and incident_state["memory_leak"]:
            incident_state["memory_leak"] = False

            save_alert({
                "timestamp": now_iso(),
                "type": "memory_leak",
                "severity": "warning",
                "message": "Memory stabilized"
            })

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)