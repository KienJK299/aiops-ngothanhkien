# 1. **Which similarity function did you choose for Layer 2, and why?** Reference at least one alternative you considered and an empirical reason for choosing the one you did.

Hệ thống sử dụng phương pháp Cosine Similarity kết hợp Multi-field Tokenization để so sánh giữa Sự cố hiện tại và history.
Đã cân nhắc Jaccard Distance dựa trên tập hợp từ khóa log thô nhưng vì nó hoàn toàn bỏ qua tần suất xuất hiện của các log template giống nhau nên đã không sử dụng

Tại incident E01, nhờ Cosine Similarity, hệ thống nhận diện được INC-2025-11-08 có `similarity = 0.596` nhờ khớp chính xác cả cấu trúc đồ thị trace `(trace match = 0.989)` và chỉ số metric `(metrics match = 0.815)`

# 2. **How does outcome-weighted voting change the candidate ranking versus a pure-similarity ranking?** Demonstrate with a concrete eval incident.

Với E05, Nếu sd pure-similarity ranking, INC-2025-09-05 gần nhất với `similarity = 0.623` thực hiện cả hai hành động: rollback_service và increase_pool_size nhưng với outcome-weighted voting thì sẽ chọn đc rollback_service

`"Outcome-weighted action votes: {\"increase_pool_size\": 0.794, \"page_oncall\": 0.065, \"restart_pod\": 0.29, \"rollback_service\": 1.04}."`

# 3. **For one eval incident, explain the EV calculation in full** — the candidate set, weights, P_success values, costs, and which action won and by how much.

### 3. Giải trình chi tiết cách tính Giá trị Kỳ vọng (EV - Expected Value) cho Incident E01
Dưới đây là toàn bộ tiến trình tính toán toán học động để đưa ra quyết định cho sự cố E01:

* Tập hợp ứng viên đề xuất từ KNN: [rollback_service, increase_pool_size, restart_pod, page_oncall]
* Trọng số và Giá trị biểu quyết lũy kế thu được (Votes Summary):
    * V_rollback_service = 0.941
    * V_increase_pool_size = 0.828
    * V_page_oncall = 0.076
    * V_restart_pod = 0.047
* Tính toán Điểm đồng thuận (Consensus Score) và Độ tự tin (Confidence):
    * Tổng số phiếu bầu thực tế: 0.941 + 0.828 + 0.076 + 0.047 = 1.892
    * Score_consensus (rollback_service) = 0.941 / 1.892 = 0.498
    * Độ tự tin cuối cùng dựa trên hàm kết hợp tuyến tính với vị trí tương đồng nhất (best_similarity = 0.596):
      Confidence = (0.498 * 0.55) + (0.596 * 0.75) = 0.2739 + 0.447 = 0.721
* Hành động chiến thắng: rollback_service giành chiến thắng tuyệt đối trước increase_pool_size với khoảng cách cách biệt về điểm vote là 0.113.

# 4. **When did your engine choose to escalate (page_oncall) instead of auto-act?** Was that choice correct against the eval ground truth?

* **OOD**
    * *Tiêu chuẩn:* Độ tương đồng cao nhất nhỏ hơn 0.12 và tổng điểm vote tối đa nhỏ hơn 0.08.
    * *Thực tế tại E02:* Log chứa lỗi chứng chỉ và TLS handshake, điểm KNN trả về độ tương đồng cực thấp. Hệ thống kích hoạt **Human gate**, chuyển trạng thái sang page_oncall với lý do: *"Certificate/TLS rotation requires manual privilege escalation."*
* **Đánh giá độ chính xác:**. E02 đã đưa ra đúng action là `"page_oncall"`

# 5. **What is the most likely class of incident that breaks your engine?** Propose one concrete improvement that would help, but explain why you did not implement it within the time budget.

* **Lớp sự cố gây lỗi cao nhất:** **(Stealthy Cascading Dependency Exhaustion)**. Đây là dạng sự cố mà một dịch vụ ở sâu trong hệ thống (như một Database bên thứ ba hoặc Core Banking cũ) bị treo, khiến các dịch vụ trung gian phía trên bị đầy Connection Pool. Khi đó, log thu thập được từ các dịch vụ API Gateway phía trên sẽ ngập tràn từ khóa "PoolExhaustedException", đánh lừa thuật toán KNN bỏ qua lỗi gốc để chọn increase_pool_size.
* **Đề xuất cải tiến:** Tích hợp thuật toán **(Granger Causality)** nhằm tính toán độ trễ chênh lệch (p99 latency delta) giữa các nút.
