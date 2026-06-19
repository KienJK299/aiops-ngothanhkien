# DESIGN.md — Ronki Closed-Loop Orchestrator

## 1. Decision engine: Rule-based hay LLM-based?

**Lựa chọn: Rule-based.**

**Lý do & Ngữ cảnh hệ thống:**
Hệ thống sản xuất của **Ronki** vận hành với 5 microservices xử lý ~80,000 orders/ngày. Mã nguồn orchestrator định nghĩa một tập hợp gồm 3 loại alerts cố định, tường minh (`HighLatency`, `HighErrorRate`, `InstanceDown`) và tiến hành ánh xạ trực tiếp `alertname` qua dict `cfg.get("runbook_map", {})` để lấy ra runbook tương ứng (`restart_service.sh`, `clear_cache.sh`). 

Trong một hệ thống closed-loop tự động hóa hoàn toàn, tính **predictable (dự đoán được)** và **reliability (độ tin cậy)** là ưu tiên tối thượng nhằm tránh gây sập dây chuyền hạ tầng (cascade failure) trong các khung giờ cao điểm (11:00–13:00, 19:00–22:00).

**Trade-offs (Đánh đổi kỹ thuật):**

| Tiêu chí | Rule-based (Lựa chọn) | LLM-based (Thay thế) |
| :--- | :--- | :--- |
| **Decision Latency** | **Cực thấp (< 1ms)** | Cao (200ms – 800ms do API round-trip network) |
| **Tính Deterministic** | **100%** (Cùng một alert luôn ra một quyết định giống nhau) | Biến động (Phụ thuộc vào prompt, temperature, rủi ro hallucination) |
| **Chi phí vận hành** | Không tốn chi phí | Phụ thuộc bên thứ ba (Anthropic API: ~$0.002–$0.01/quyết định) |
| **Khả năng mở rộng** | Kém (Mỗi khi có alert mới phải cập nhật `config.yaml` thủ công) | Tốt (Có khả năng suy luận ngữ cảnh tự nhiên nếu prompt đủ tốt) |
| **Cơ chế Fallback** | Không cần thiết | Bắt buộc phải viết kèm Rule-based fallback đề phòng API sập |

**Kết luận:** Với quy mô 3 alert types của bài lab, Rule-based mang lại sự an toàn tuyệt đối. Nếu trong tương lai hệ thống mở rộng lên nhiều alert phức tạp với mô tả ngôn ngữ tự nhiên, chúng ta mới cân nhắc chuyển sang LLM-based đi kèm điều kiện cấu hình `confidence >= 0.6`.

---

## 2. Blast-radius config

Cấu hình giới hạn phạm vi ảnh hưởng (Blast-radius) được nạp trực tiếp qua file YAML và khởi tạo đối tượng `BlastRadiusGuard`:

```yaml
blast_radius:
  max_actions_per_minute: 3
  max_restarts_per_service_per_hour: 5
Lý do chọn các con số cụ thể này:
```

max_actions_per_minute: 3: Hệ thống Ronki có tổng cộng 5 services. Khi xảy ra lỗi cascading (trung bình 2 lần/tuần), các alert sẽ bắn dồn dập. Việc giới hạn tối đa 3 hành động khắc phục trong 1 phút giúp orchestrator đủ không gian xử lý song song các lỗi trên các dịch vụ khác nhau nhưng ngăn chặn tình trạng thundering herd (Tất cả services bị restart đồng loạt gây quá tải ngược lên tầng Database/Gateway).

max_restarts_per_service_per_hour: 5: Nếu một service đơn lẻ bị crash-loop và kích hoạt hàm guard.check(service) đến lần thứ 5 trong vòng một giờ mà trạng thái vẫn không phục hồi, điều đó chứng tỏ đây là một lỗi nghiêm trọng không mang tính tạm thời (non-transient fault). Việc tiếp tục restart vô hạn là vô ích, orchestrator cần dừng lại, ghi log BLAST_RADIUS_EXCEEDED để giữ nguyên hiện trường cho kỹ sư on-call can thiệp thủ công.

## 3. Verify step
Metric kiểm tra độc lập (Cấu hình qua verify_policy trong file YAML):

HighLatency: Kiểm tra metric latency_p99 so với ngưỡng trần thông qua hàm verify_service.

HighErrorRate: Kiểm tra error_rate_pct.

InstanceDown: Kiểm tra metric sinh tồn up.

Ngưỡng Threshold nguồn (Nạp động từ data/baseline.json):

Ngưỡng được trích xuất động qua baseline["verify_thresholds"] thay vì hardcode trong logic xử lý.

Ví dụ với Latency: Chọn ngưỡng trần 500ms (gấp ~2 lần đỉnh của checkout-svc: 230ms trong file baseline) giúp hệ thống đủ linh hoạt tránh các đỉnh nhiễu ngắn hạn (false negative) nhưng phát hiện chính xác nếu hành động khắc phục thất bại.

Cấu hình Timing chi tiết:

verify_timeout_seconds: 60 (Nạp từ baseline.json): Chu kỳ khởi động lại container thực tế mất 5-10s, kết hợp với chu kỳ Scrape mặc định của Prometheus là 10s. Do đó cần khoảng thời gian 60 giây để metric thu thập về Prometheus ổn định.

verify_poll_interval_seconds: 10: Đồng bộ hoàn toàn với Prometheus scrape interval để không lãng phí tài nguyên truy vấn API.

verify_min_samples: 3: Quy tắc 3 mẫu liên tiếp: Hệ thống bắt buộc phải ghi nhận ít nhất 3 sample liên tục đều vượt qua bài kiểm tra (PASS) mới đưa ra kết luận. Điều này triệt tiêu hoàn toàn trường hợp false thành công do một khoảnh khắc may mắn hệ thống phản hồi nhanh đột xuất.

## 4. Circuit breaker reset
Reset Mode: Manual (Thủ công).

Lý do thiết kế an toàn:
Vòng lặp chính while True của orchestrator sẽ liên tục kiểm tra trạng thái mạch thông qua hàm cb.is_open(). Khi phát hiện 3 thất bại liên tiếp (bao gồm lỗi dry-run, lỗi thực thi runbook hoặc lỗi verify không đạt), mạch chuyển sang trạng thái mở và lập tức đóng băng toàn bộ hoạt động automation bằng cách nhảy vào nhánh continue kèm log lỗi treo mạch:

```json
{"ts":"2026-06-19T08:06:23.000000+00:00","level":"ERROR","logger":"orchestrator","event_type":"CIRCUIT_BREAKER_HALT","service":"","action":"poll","result":"halted","message":"Circuit open; polling suspended."}
```
Nếu sử dụng cơ chế tự động reset sau một khoảng thời gian (Automatic Reset), hệ thống sẽ đối mặt với rủi ro rơi vào một vòng lặp lỗi vô hạn (infinite failure loop) nếu nguyên nhân gốc rễ chưa được triệt tiêu hoàn toàn. Việc tự động hóa chạy lại các hành động lỗi có thể gây cạn kiệt kết nối database, làm treo gateway, biến một sự cố microservice đơn lẻ thành thảm họa sập toàn bộ hệ thống e-commerce.

Quy trình Reset thủ công thực tế:

Mạch mở, đóng băng toàn bộ tự động hóa hạ tầng.

Kỹ sư On-call nhận Alert, kiểm tra log hệ thống qua Grafana/Audit logs để tìm nguyên nhân gốc rễ và tiến hành xử lý.

Sau khi xác nhận hệ thống đã an toàn, tiến hành khởi động lại orchestrator bằng lệnh:

```Bash
uv run python closed_loop.py --config config.yaml
```

## 5. Mutex strategy (Xử lý Race Condition khi nhận Alerts đồng thời)
Thiết kế kỹ thuật:
Để xử lý kịch bản đồng thời (Stress Scenario #5), orchestrator thiết lập một cơ chế khóa dịch vụ bằng cách duy trì một dictionary chứa các threading.Lock() riêng biệt tương ứng với từng tên service (_service_locks), được bảo vệ bởi một lock luồng tổng _service_locks_guard trong hàm get_service_lock(service).

Khi các luồng xử lý chạy song song thông qua ThreadPoolExecutor, tiến trình xử lý gọi phương thức service_lock.acquire(blocking=False).

Nếu Service B đang chạy runbook phục hồi, các alert trùng lặp đổ về cho Service B trong chu kỳ đó sẽ lập tức trả về kết quả False, ghi log SERVICE_LOCK_BUSY và bỏ qua ngay lập tức.

Cơ chế khóa phân tách theo Service Name đảm bảo hai dịch vụ khác nhau hoàn toàn (ví dụ payment-svc và inventory-svc) luôn sở hữu 2 lock độc lập, cho phép chạy phục hồi song song hoàn toàn độc lập mà không block nhau.

## 6. Rollback chain ordering (Xử lý lỗi Multi-step Deploy)
Thiết kế kỹ thuật:
Để xử lý kịch bản giao dịch nhiều bước (Stress Scenario #4), hàm run_transactional_steps thực thi chuỗi hành động theo thứ tự tuần tự và tích lũy danh sách các bước đã hoàn thành thành công vào một mảng completed_steps.

Nếu xảy ra lỗi tại bất kỳ bước nào trong chuỗi, hệ thống sẽ trích xuất danh sách các bước rollback tương ứng từ cfg["multi_step_rollback_map"] và thực hiện duyệt đảo ngược mảng bằng từ khóa reversed(rollback_steps[: len(completed)]). Quy trình bóc tách trạng thái sẽ đi ngược lại: Rollback bước sau trước, bước trước sau. Những bước chưa từng chạy thành công sẽ tuyệt đối không gọi lệnh rollback.

Lý do áp dụng nguyên lý LIFO (Last In, First Out):
Tương tự như cơ chế transactional rollback trong các hệ quản trị cơ sở dữ liệu, bước A (ví dụ: ngắt điều hướng traffic) tạo tiền đề trạng thái cho bước B (áp dụng cấu hình mới). Nếu tiến hành rollback A trước B, dịch vụ sẽ lập tức phải hứng chịu traffic từ người dùng trong khi cấu hình bên dưới đang ở trạng thái không nhất quán, lỗi cấu trúc nghiêm trọng sẽ xảy ra. Việc teardown bắt buộc phải đi ngược chu trình setup.

## 7. Decision validation policy (Chống LLM Hallucination / Lỗi Cấu hình)
Thiết kế kỹ thuật:
Để bảo vệ hệ thống trước các lỗi ảo giác (Hallucination) từ bộ ra quyết định (Stress Scenario #6), orchestrator tích hợp hàm kiểm tra chặt chẽ validate_runbook ngay sau khi khớp mẫu alert và trước khi bước DRY-RUN diễn ra.

Hệ thống sẽ đối chiếu đường dẫn của runbook nhận được với danh sách trắng whitelist được khai báo tường minh trong runbook_registry hoặc runbook_map:

Nếu tên runbook lạ hoặc không nằm trong danh sách trắng, hệ thống lập tức chặn đứng, ghi log sự kiện cấu trúc DECISION_VALIDATION_FAILED kèm các trường dữ liệu bắt buộc: bad_runbook, alertname, raw_decision, và hành động result="escalate_no_auto_action".

Tiến trình xử lý kết thúc ngay lập tức: Không spawn subprocess bừa bãi, không tính lỗi này vào bộ đếm Circuit Breaker (cb.record_failure()) để tránh làm mở mạch oan uổng khi lỗi không thuộc về hạ tầng.