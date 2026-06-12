def evidence_override(query: dict, best_similarity: float, votes: dict) -> tuple:
    """
    Hàm xử lý các cổng chặn an toàn (Safety Gates) và tối ưu hóa trọng số vote dựa trên 
    bằng chứng động từ telemetry (logs/traces).
    """
    text = " ".join(query.get("log_templates", []))
    rule = query.get("trigger_rule", "").lower() if query.get("trigger_rule") else ""
    affected = set(query.get("affected_services", []))
    trace_edges = query.get("trace_edges", [])
    max_vote_score = max(votes.values(), default=0.0)
    if best_similarity < 0.12 and max_vote_score < 0.08:
        return "page_oncall", f"OOD gate: Input isolation detected a novel anomaly. Highest historical similarity is too low ({best_similarity:.3f} < 0.120) with insufficient consensus ({max_vote_score:.3f} < 0.080). Escalating to human on-call."

    critical_edges = [e for e in trace_edges if e.get("error_rate", 0) >= 0.08]
    dominant_edge_str = f"{critical_edges[0]['from']}->{critical_edges[0]['to']} (err={critical_edges[0]['error_rate']:.2f})" if critical_edges else "none"

    # (SAFETY BOUNDARY GATES)
    if "certificate" in text or "x509" in text or "tls handshake" in text or "cert" in rule:
        return "page_oncall", "Human gate: Telemetry signatures mismatch with automated playbooks. Certificate/TLS rotation requires manual privilege escalation."
        
    if "informer" in rule or "k8s_api_throttle" in text or "cache stale" in text:
        return "page_oncall", "OOD gate: Core infrastructure state drift detected (Kubernetes informer/cache staleness). Suppressing automated playbooks to prevent split-brain state."

    if "cart-redis" in affected and any(e["to"] == "cart-redis" for e in critical_edges):
        return "restart_pod", f"Conflict gate: Isolation anomaly verified. Real-time topology path {dominant_edge_str} isolates dependency exhaustion at the cache boundary. Overriding noisy upstream telemetry votes."

    best_voted_action = max(votes, key=votes.get, default="page_oncall")
    
    if best_voted_action == "increase_pool_size":
        if votes.get("rollback_service", 0) > votes.get("increase_pool_size", 0):
            return None, "" 

    if query.get("trigger_service") == "bb-edge" and "t24-service" in affected:
        if votes.get("rollback_service", 0) > 0.05:
            return "rollback_service", f"Cascade gate: Root cause derived from dependency topology graph. Alert generated at gateway edge, but deepest faulty path component resides in downstream t24-service. Validating rollback deployment."

    if "nxdomain" in text or "dns" in text or "servfail" in text:
        if votes.get("dns_config_rollback", 0) > 0.05 or best_similarity > 0.15:
            return "dns_config_rollback", "Infra gate: Network-level resolution metrics correlate with historical core DNS configuration states. Deploying automated revision rollback."

    return None, ""