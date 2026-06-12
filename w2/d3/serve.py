import os
import time
import json
import numpy as np
import networkx as nx
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dateutil.parser import parse
from fastapi import FastAPI, HTTPException, Request, Response, status

AIOPS_USE_LLM = os.getenv("AIOPS_USE_LLM", "false").lower() == "true"

app = FastAPI(
    title="AIOps Alert Correlation & RCA API",
    description="Production-ready endpoint for incident correlation and root cause analysis.",
    version="1.2.0"
)

# Global variables để lưu trữ Topology Graph và History Map (InMemory Cache)
GLOBAL_GRAPH = nx.DiGraph()
HISTORY_DATA: Dict[str, Any] = {"incidents": []}

# Biến lưu trữ metadata của Graph cho endpoint /version
GRAPH_METADATA = {
    "app": "1.2.0",
    "graph_version": "g-2026060801",
    "graph_loaded_at": "2026-06-08T03:14:22Z",
    "graph_source": "otel-tempo",
    "graph_node_count": 14,
    "graph_edge_count": 17
}
# 2. PYDANTIC SCHEMAS (DATA VALIDATION)
class AlertSchema(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: int
    labels: Optional[Dict[str, Any]] = Field(default_factory=dict)

class IncidentRequest(BaseModel):
    alerts: List[AlertSchema]
    gap_sec: Optional[int] = 49
    max_hop: Optional[int] = 1

# 3. CORE LOGIC (CORRELATION & RCA)

def fingerprint(alert: Dict[str, Any]) -> str:
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"

def session_groups(alerts: List[Dict[str, Any]], gap_sec: int) -> List[List[Dict[str, Any]]]:
    if not alerts:
        return []
    sorted_alerts = sorted(alerts, key=lambda a: a['ts'])
    groups = [[sorted_alerts[0]]]
    for alert in sorted_alerts[1:]:
        last_ts = parse(groups[-1][-1]['ts'])
        if (parse(alert['ts']) - last_ts).total_seconds() <= gap_sec:
            groups[-1].append(alert)
        else:
            groups.append([alert])
    return groups

def topology_group(alerts: List[Dict[str, Any]], graph: nx.Graph, max_hop: int) -> List[List[Dict[str, Any]]]:
    undirected = graph.to_undirected()
    by_service = {}
    for a in alerts:
        by_service.setdefault(a['service'], []).append(a)

    services = list(by_service.keys())
    parent = {s: s for s in services}
    
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, s1 in enumerate(services):
        for s2 in services[i+1:]:
            try:
                if s1 in undirected and s2 in undirected:
                    if nx.shortest_path_length(undirected, s1, s2) <= max_hop:
                        parent[find(s1)] = find(s2)
            except nx.NetworkXNoPath:
                pass

    groups = {}
    for s in services:
        groups.setdefault(find(s), []).extend(by_service[s])
    return list(groups.values())

def run_correlation(alerts: List[Dict[str, Any]], graph: nx.Graph, gap_sec: int, max_hop: int) -> List[Dict[str, Any]]:
    sessions = session_groups(alerts, gap_sec=gap_sec)
    clusters = []
    for s_idx, session_alerts in enumerate(sessions):
        for g_idx, group in enumerate(topology_group(session_alerts, graph, max_hop)):
            clusters.append({
                'cluster_id': f'c-{s_idx:03d}-{g_idx:03d}',
                'alert_count': len(group),
                'services': sorted({a['service'] for a in group}),
                'time_range': [min(a['ts'] for a in group), max(a['ts'] for a in group)],
                'max_severity': max(a['severity'] for a in group),
                'fingerprints': sorted(set(fingerprint(a) for a in group)),
                'raw_alerts': group
            })
    return clusters

def run_rca(cluster: Dict[str, Any], all_alerts: List[Dict[str, Any]], graph: nx.DiGraph) -> List[tuple]:
    cluster_services = cluster['services']
    start_time, end_time = cluster['time_range']
    
    subgraph = graph.subgraph(cluster_services).copy()
    cluster_alerts = [a for a in all_alerts if a['service'] in cluster_services and start_time <= a['ts'] <= end_time]
    
    if subgraph.number_of_edges() > 0:
        pagerank_scores = nx.pagerank(subgraph, alpha=0.85)
    else:
        pagerank_scores = {svc: 1.0/len(cluster_services) for svc in cluster_services} if cluster_services else {}
        
    max_pr = max(pagerank_scores.values()) if pagerank_scores else 1.0
    earliest_time = min(a['ts'] for a in cluster_alerts) if cluster_alerts else None
    scores = {}
    
    for svc in cluster_services:
        pr_val = pagerank_scores.get(svc, 0) / max_pr
        out_degree = subgraph.out_degree(svc) if svc in subgraph else 0
        terminal_bonus = 0.05 if out_degree == 0 else 0.0

        svc_alerts = [a for a in cluster_alerts if a['service'] == svc]
        if not svc_alerts:
            t_score = 0.5
        else:
            first_alert = min(a['ts'] for a in svc_alerts)
            t_score = 1.0 if first_alert == earliest_time else 0.5
            
        scores[svc] = (0.6 * pr_val) + (0.4 * t_score) + terminal_bonus
        scores[svc] = min(scores[svc], 1.0)
        
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def get_similar_incidents(cluster: Dict[str, Any], history: Dict[str, Any]) -> List[Dict[str, Any]]:
    incidents_list = history.get('incidents', [])
    scores = []
    cluster_svcs = set(cluster['services'])
    
    for h in incidents_list:
        h_svcs = set(h.get('services_involved', []))
        c_score = 0.4 if h.get('root_cause_service') in cluster_svcs else 0.0
        overlap = len(cluster_svcs & h_svcs)
        t_score = min(0.4, 0.2 * overlap)
        s_score = 0.2 if h.get('severity') == cluster.get('max_severity') else 0.0
        
        total_score = c_score + t_score + s_score
        if total_score >= 0.2:
            scores.append(({
                "incident_id": h.get('id'),
                "root_cause_class": h.get('root_cause_class', 'unknown'),
                "remediation_actions": h.get('remediation', ["Investigate logs manually"])
            }, total_score))
            
    sorted_history = sorted(scores, key=lambda x: x[1], reverse=True)
    return [item[0] for item in sorted_history]

# 4. MIDDLEWARE & LIFECYCLE

@app.on_event("startup")
def startup_event():
    """Nạp dữ liệu Graph và History vào memory khi khởi động Server."""
    global GLOBAL_GRAPH, HISTORY_DATA, GRAPH_METADATA
    
    services_path = 'dataset/services.json'
    history_path = 'dataset/incidents_history.json'
    
    if os.path.exists(services_path):
        with open(services_path, 'r', encoding='utf-8') as f:
            s_map = json.load(f)
            for svc in s_map.get('services', []):
                GLOBAL_GRAPH.add_node(svc['name'], type='service', criticality=svc.get('criticality'))
            for store in s_map.get('stores', []):
                GLOBAL_GRAPH.add_node(store['name'], type='store', criticality=store.get('criticality'))
            for edge in s_map.get('edges', []):
                GLOBAL_GRAPH.add_edge(edge['from'], edge['to'], type=edge.get('type'))
                
        # Cập nhật số node/edge thực tế nếu file json có nhiều dữ liệu hơn, ngược lại giữ default mẫu
        if GLOBAL_GRAPH.number_of_nodes() > 0:
            GRAPH_METADATA["graph_node_count"] = GLOBAL_GRAPH.number_of_nodes()
            GRAPH_METADATA["graph_edge_count"] = GLOBAL_GRAPH.number_of_edges()
    
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            HISTORY_DATA = json.load(f)

@app.middleware("http")
async def add_latency_header(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Response-Time-Ms"] = f"{process_time * 1000:.2f}"
    return response

# 5. ENDPOINTS

@app.get("/healthz", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok"}

@app.get("/readyz", status_code=status.HTTP_200_OK)
def ready_check():
    if GLOBAL_GRAPH.number_of_nodes() == 0:
        raise HTTPException(status_code=503, detail="System not ready: Topology graph empty")
    return {"status": "ready"}

@app.get("/version", status_code=status.HTTP_200_OK)
def get_version():
    return GRAPH_METADATA

@app.post("/incident", status_code=status.HTTP_200_OK)
async def process_incident(payload: IncidentRequest):
    try:
        raw_alerts = [alert.dict() for alert in payload.alerts]
        
        # 1. Run Correlation pipeline
        clusters = run_correlation(raw_alerts, GLOBAL_GRAPH, payload.gap_sec, payload.max_hop)
        
        results = []
        # 2. Run RCA & History matching cho từng cluster tìm được
        for cluster in clusters:
            candidates = run_rca(cluster, raw_alerts, GLOBAL_GRAPH)
            top_candidate = candidates[0] if candidates else ("unknown", 0.0)
            
            history_matches = get_similar_incidents(cluster, HISTORY_DATA)
            
            if history_matches:
                best_match = history_matches[0]
                remediation = best_match.get('remediation_actions', [])
                root_cause_class = best_match.get('root_cause_class', 'unknown')
                matched_id = best_match.get('incident_id')
            else:
                remediation = ["Investigate logs manually", "Check system metrics"]
                root_cause_class = "unknown"
                matched_id = "NONE"
                
            results.append({
                "cluster_id": cluster["cluster_id"],
                "services_involved": cluster["services"],
                "root_cause": top_candidate[0],
                "confidence": round(float(top_candidate[1]), 2),
                "root_cause_class": root_cause_class,
                "recommended_actions": remediation,
                "reasoning": f"Triggered by {top_candidate[0]} based on graph PageRank and temporal sequence. Matched template: {matched_id}"
            })
            
        return {
            "total_alerts": len(raw_alerts),
            "clusters_detected": len(results),
            "analysis_results": results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=f"Pipeline Processing Error: {str(e)}"
        )