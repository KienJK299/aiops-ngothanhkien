# FINDINGS: Root Cause Analysis & Auto-Remediation Report

## 1. Phân tích các Cluster chính (Root Cause & Lý do)

### Cluster `c-000-000`
- Root Cause: `payment-svc` class: `connection_pool_exhaustion`.
`payment-svc` thỏa mãn tuyệt đối cả hai chiều: Temporal (bắn alert sớm nhất cụm lúc sự cố bắt đầu kích hoạt) và Topology (nút thắt cổ chai nhận toàn bộ dòng lỗi lan truyền ngược từ các service khác như `checkout.svc`). Việc cạn kiệt connection pool tại đây làm nghẽn toàn bộ luồng checkout của GeekShop. Đồng thời nó cũng có Heuristic Score cao `0.8` thể hiện incident này đã xảy ra trong quá khứ

## 2. Đánh giá Confidence — Có dám deploy Auto-Remediation không?

`confidence` của cả hai cluster trên đều đạt `1.0` cộng với Heuristic Score đạt mức ổn với `0.8` và `0.6`
Do đó, hệ thống hoàn toàn đủ cơ sở tin cậy để tự động kích hoạt các(`actions`) như: tự động Rollback phiên bản lỗi về `v3.1`/`v3.0`, tự động nâng dung lượng connection pool, hoặc chèn lệnh giải phóng bộ nhớ `gc.collect()` mà không cần đợi kỹ sư xác nhận, giúp giảm thiểu tối đa chỉ số MTTR (thời gian phục hồi hệ thống).


## 3. Một trường hợp hệ thống KHÔNG CHẮC CHẮN (Unsure Case)

TH unsure sẽ rơi vào nếu như hệ thống xuất hiện một sự cố mới hoàn toàn (Zero-day incident) chưa từng có trong lịch sử.

Điểm tương đồng (H-Score) chạm đáy: Vì thuật toán kNN/Heuristic hoạt động dựa trên việc so khớp sự trùng lặp (Overlap) của vùng ảnh hưởng sự cố trong quá khứ. Khi gặp một pattern lỗi mới tinh, tập hợp các service bắn alert sẽ không khớp với bất kỳ Incident ID nào có sẵn, khiến điểm H-Score sụt giảm nghiêm trọng (dưới mức 0.4).

Mất phương hướng "bốc thuốc": Khi điểm tương đồng quá thấp, classifier không thể định danh chính class, và quan trọng nhất là hệ thống không thể thực hiện được các actions an toàn từ quá khứ để thực thi.

## 4. Bonus Path Evaluation: Heuristic vs. TF-IDF Retrieval

| CLUSTER ID | H-SCORE (Heuristic) | T-SCORE (TF-IDF) | BEST HISTORICAL MATCH |
| :--- | :---: | :---: | :--- |
| c-000-000 | 0.8000 | 0.4399 | `INC-2025-11-08` |
| c-000-001 | 0.6000 | 0.4613 | `INC-2025-08-02` |

Cả hai phương pháp (Heuristic và TF-IDF) đều cho ra được kết quả Best Match, lần lượt chỉ ra `INC-2025-11-08` và `INC-2025-08-02` là template sửa lỗi tối ưu. Nhưng phương pháp Heuristic cho ra kết quả với score cao hơn rất nhiều so với TD-IDF