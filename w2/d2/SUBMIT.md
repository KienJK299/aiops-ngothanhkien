# Confidence của top-1 trong cluster lớn nhất bạn xử lý là bao nhiêu? Nếu phải set threshold để auto-rollback (không cần SRE confirm), bạn pick số nào? Lý do?

- Top-1 trong cluster lớn nhất mà em đã xử lý là c-000-000 với confidence là 1.0, và dự đoán được root cause đến từ payment-svc. 
- Nếu phải set threshold để auto-rollback (không cần SRE confirm), em sẽ chọn threshold khoảng 0.85 đến 0.9 vì để đạt đến mức threshold này thì nó cần thỏa mãn cả 2 điều kiện đầu tiên lf Temporal (service này phải nằm trong nhóm phát báo động sớm nhất), thứ hai là Topology (node này có điểm PageRank cao, là trung tâm chịu áp lực nơi mà nếu nó sập thì sẽ có nhiều service khác bị kéo theo).

# Variant bạn chọn cho classifier (A rule-based / B free LLM / C paid LLM). Chạy thực tế ra sao? Trade-off với variant bạn không chọn?

- Em chọn rule-based với retrieval-based classifier theo kiểu kNN. 
- Pipeline sẽ retrieve top 3 similar incidents bằng keyword similarity, sau đó lấy class và actions từ top 1 incident giống nhất. 
- Khi chạy thực tế:

    - Cluster c-000-001 trả về incident `{"id": "INC-2025-11-08", "ts": "2025-11-08T10:15:00Z", "severity": "critical", "services_involved": ["payment-svc", "payments-db", "checkout-svc"], "root_cause_service": "payment-svc",  "root_cause_class": "connection_pool_exhaustion", "summary": "Payment-svc v3.2 deploy at 09:42 leak DB pool. Pool 50/50 used trong 5 phút. Downstream checkout cascade. Notification queue backed up.", "remediation": "Rollback to v3.1. Scale pool 50 → 100 cushion. Add pool monitor alert > 80%.",     "mttd_min": 3,  "mttr_min": 19}`

    - Cluster c-000-001 trả về incident `{"id": "INC-2025-08-02", "ts": "2025-08-02T15:32:00Z", "severity": "medium", "services_involved": ["recommender-svc"], "root_cause_service": "recommender-svc","root_cause_class": "memory_leak", "summary": "Recommender OOM mỗi 4h sau deploy v3.1. Pandas DataFrame không release giữa request.", "remediation": "Patch leak; rollback v3.0 trong khi chờ. Add gc.collect() trong handler.", "mttd_min": 45, "mttr_min": 90}`


- Variant này đơn giản, dễ thực hiện và không cần API key. Tuy nhiên, trade-off lớn nhất ở đây là nó phụ thuộc vào độ chính xác của incident history, nếu như thiếu do các pattern quá mới không có trong incident history vậy thì sẽ dẫn đến score và confidence thấp không quá đáng tin

# Đọc bảng Industry landscape (§6) — pipeline bạn xây gần product nào nhất? Trong domain GeekShop (e-commerce, alert volume cao, service map tương đối ổn định), lựa chọn đó hợp lý hay nên đổi?

- Pipeline được build xây gần với hướng của Dynatrace Davis nhất, vì nó không đoán mò dựa trên thống kê thuần túy, mà dùng Subgraph Traversal và PageRank trực tiếp trên bản đồ microservices kết hợp với trục thời gian (Temporal) để tìm ra root cause

- Trong domain GeekShop (e-commerce, alert volume cao, service map tương đối ổn định), lựa chọn này vẫn hợp lý. Vì bản đồ dịch vụ của GeekShop ít thay đổi, các mối quan hệ Upstream/Downstream giữa các microservices (như edge-lb --> checkout-svc --> payment-svc) là cố định và đáng tin cậy. Việc dùng đồ thị để truy vết dòng lỗi sẽ cho độ chính xác gần như tuyệt đối, không lo bị bẫy "bản đồ cũ" làm sai lệch điểm PageRank.