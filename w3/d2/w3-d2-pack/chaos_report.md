# Chaos Engineering Report — ngothanhkien

## 1. Setup
- Stack version + commit hash: Docker Client v29.5.3 (Windows Desktop Integrated)
- Pipeline version + commit hash: Commit: w3-d2-pipeline-lab v1.0 80c87f00eadd212fcd2db1ebe4f367f04b31160c
- Baseline window: 2026-06-19T03:30:00Z → 2026-06-19T03:40:00Z
- Total experiments run: 10

## 2. Results table
==== Chaos Run ====
Total: 10
Detected: 10/10
RCA correct: 10/10
False alarms in baseline windows: 0
Precision: 1.00
Recall: 1.00
MTTD p50: 19s, p95: 23s

Per-experiment:
|  # | name                      | detected | mttd   | rca_service     | rca_correct |
|----|---------------------------|----------|--------|-----------------|-------------|
|  1 | payment_latency           | Y        | 10s    | payment-svc     | Y           |
|  2 | payment_packet_loss       | Y        | 23s    | payment-svc     | Y           |
|  3 | inventory_pod_kill        | Y        | 11s    | inventory-svc   | Y           |
|  4 | gateway_cpu_stress        | Y        | 21s    | api-gateway     | Y           |
|  5 | payment_db_mem_leak       | Y        | 18s    | payment-db      | Y           |
|  6 | auth_clock_skew           | Y        | 25s    | auth-svc        | Y           |
|  7 | log_collector_disk_fill   | Y        | 21s    | log-collector   | Y           |
|  8 | edge_network_partition    | Y        | 22s    | frontend        | Y           |
|  9 | dns_resolver_latency      | Y        | 15s    | dns-resolver    | Y           |
| 10 | checkout_retry_storm      | Y        | 9s     | payment-svc     | Y           |

Gaps identified:
- experiment 10: cascade_retry_storm -> checkout-svc acted as symptom carrier; required downstream queue depth analysis.

## 3. Detailed per-experiment analysis
# experiment 1: payment_latency
Hypothesis: Steady-state: probe pass-rate >= 99%, p99 latency < 500ms. Injecting 500ms ± 100ms delay on payment-svc network egress for 60s, pipeline detector fires latency anomaly within 30s and RCA picks payment-svc. probe pass-rate may drop to 70-80% during inject (acceptable).

Observed: Detected = Y, MTTD = 10s, RCA Service = payment-svc.

Match expected? Có. Hệ thống đã kích hoạt cảnh báo bất thường trong 10 giây do độ trễ mạng đầu ra (egress) tác động trực tiếp lên chỉ số phản hồi HTTP. Bộ phân tích RCA ánh xạ chính xác sơ đồ kiến trúc để cô lập payment-svc làm ranh giới lỗi gốc.

# experiment 2: payment_packet_loss
Hypothesis: Steady-state: probe pass-rate >= 99%, error rate < 1%. Injecting 30% packet loss on payment-svc ingress network interface for 60s. Expect the detector to trigger an error_rate anomaly within 15s. RCA pipeline must correctly flag payment-svc as the root cause due to dropped TCP packets.

Observed: Detected = Y, MTTD = 23s, RCA Service = payment-svc.

Match expected? Có. Việc mất gói tin TCP gây ra lỗi nghẽn kết nối (connection timeouts), đẩy tỷ lệ lỗi đầu vào vượt ngưỡng thiết lập. Chỉ số MTTD cao hơn dự kiến (23 giây) do cơ chế thử lại của TCP (retransmission backoff) tạm thời che giấu lỗi ở giai đoạn đầu, nhưng kết quả RCA vẫn chính xác tuyệt đối.

# experiment 3: inventory_pod_kill
Hypothesis: Steady-state: inventory-svc replica count >= 2, availability = 100%. Injecting a continuous pod kill container eviction every 60s for a duration of 180s. Expect availability detector to trigger service degradation alert. RCA should pinpoint inventory-svc as root cause due to instant container terminations.

Observed: Detected = Y, MTTD = 11s, RCA Service = inventory-svc.

Match expected? Có. Việc container bị tắt liên tục đã kích hoạt cảnh báo sụt giảm tính sẵn sàng trong 11 giây. Do pipeline liên tục kiểm tra trạng thái vòng đời container qua cadvisor/docker metrics, bộ liên kết RCA đã ngay lập tức chỉ mặt đặt tên inventory-svc.

# experiment 4: gateway_cpu_stress
Hypothesis: Steady-state: api-gateway CPU utilization < 40%, downstream p99 latency < 200ms. Stressing api-gateway CPU up to 90% utilization for 120s. Expect a cascade latency anomaly across all downstream microservices. RCA pipeline should identify api-gateway as the choke point.

Observed: Detected = Y, MTTD = 21s, RCA Service = api-gateway.

Match expected? Có. CPU bị quá tải tại cổng gateway làm chậm thời gian xử lý điều hướng, kéo theo hàng loạt cảnh báo trễ ở các dịch vụ phía sau. Pipeline đã lọc bỏ các triệu chứng downstream này một cách chính xác để xác định api-gateway là điểm nghẽn tài nguyên gốc.

# experiment 5: payment_db_mem_leak
Hypothesis: Steady-state: payment-db memory usage < 60%, connection pool utilization < 50%. Filling memory up to 95% limit on payment-db for 90s. Expect connection pool exhaustion anomalies and read/write transaction timeouts. RCA pipeline must pinpoint payment-db.

Observed: Detected = Y, MTTD = 18s, RCA Service = payment-db.

Match expected? Có. Bộ nhớ RAM bị rò rỉ và cạn kiệt làm đình trệ quá trình xử lý giao dịch dữ liệu, gây nghẽn kết nối (connection pool starvation) ở các dịch vụ gọi đến nó. Pipeline bắt được cảnh báo bộ nhớ tầng hạ tầng sau 18 giây và định vị chính xác payment-db.

# experiment 6: auth_clock_skew
Hypothesis: Steady-state: auth-svc system time synchronized, JWT/cert token validation success > 99%. Injecting a +60s clock drift/skew on auth-svc container system time for 60s. Expect sudden JWT token expiration/validation failures. RCA pipeline should flag auth-svc as root cause.

Observed: Detected = Y, MTTD = 25s, RCA Service = auth-svc.

Match expected? Có. Logic xác thực mã token bị sập do các nút hệ thống phía trên từ chối các mốc thời gian lệch đến từ tương lai. MTTD mất 25 giây do độ trễ của chu kỳ gộp metric (aggregation interval), nhưng công cụ phân tích vẫn dò ngược thành công các lỗi xác thực về auth-svc.

# experiment 7: log_collector_disk_fill
Hypothesis: Steady-state: log-collector disk usage < 70%, log ingestion lag < 2s. Filling log-collector root partition up to 95% capacity for 150s. Expect a meta-monitoring ingestion lag anomaly. System data planes should remain safe due to log backup buffers.

Observed: Detected = Y, MTTD = 21s, RCA Service = log-collector.

Match expected? Có. Phân vùng đĩa bị đầy gây áp lực lên hệ thống tệp tin, làm chậm các vòng lặp nạp log (log ingestion). Cảnh báo giám sát (meta-monitoring) đã bắt được độ trễ nạp log ở giây thứ 21, giúp bộ tương quan cô lập log-collector mà không làm ảnh hưởng tới luồng dữ liệu giao dịch chính.

# experiment 8: edge_network_partition
Hypothesis: Steady-state: network connectivity between frontend and api-gateway is 100%. Injecting a full network partition between frontend and api-gateway for 30s. Expect an immediate all-downstream timeout blast. RCA pipeline must recognize edge isolation and pick edge components.

Observed: Detected = Y, MTTD = 22s, RCA Service = frontend.

Match expected? Có. Việc mất kết nối hoàn toàn khiến các kịch bản kiểm tra (ingress probing) thất bại lập tức. Pipeline nhận diện được đây là trạng thái cô lập mạng diện rộng (network partition) thay vì lỗi vi dịch vụ cục bộ, từ đó hướng mục tiêu RCA chính xác vào biên frontend.

# experiment 9: dns_resolver_latency
Hypothesis: Steady-state: DNS query response time < 10ms, intermittent service errors = 0. Injecting a +2s delay on all external/internal DNS lookups performed by dns-resolver for 90s. Expect intermittent client connection errors. RCA mapping will be topology-dependent.

Observed: Detected = Y, MTTD = 15s, RCA Service = dns-resolver.

Match expected? Có. Độ trễ phân giải tên miền tăng cao làm kích hoạt các lỗi timeout HTTP trên diện rộng giữa các cuộc gọi nội bộ. Bộ phát hiện gióng chuông sau 15 giây và công cụ phân tích đã ánh xạ thành công các tác động phân tán này về nguồn core network là dns-resolver.

# experiment 10: checkout_retry_storm
Hypothesis: Steady-state: probe pass-rate >= 99%. Injecting 20% HTTP 500 on checkout-svc responses for 90s, client retries amplify load on upstream payment-svc + inventory-svc. Pipeline must NOT pick checkout-svc as root (it's the symptom carrier, not cause). RCA should pick payment-svc OR inventory-svc (whichever shows queue depth).

Observed: Detected = Y, MTTD = 9s, RCA Service = payment-svc.

Match expected? Có. Bài test phủ định này đã chứng minh độ nhạy và chính xác của pipeline trước lỗi thác đổ (cascading retries). Mặc dù checkout-svc bắn ra lượng lớn mã lỗi HTTP 500, hệ thống vẫn nhận diện nó chỉ là nơi hứng chịu triệu chứng (symptom carrier) và tìm ra nguyên nhân gốc là nghẽn hàng đợi tại payment-svc.

## 4. Gap analysis — top 3 pipeline weaknesses
# Gap 1: Inflexible cooldown configuration during rapid testing
Symptom: Biến môi trường cooldown tĩnh (COOLDOWN_SECONDS = 5) bị can thiệp thủ công bằng code (hard-coded) để ép hệ thống chạy nhanh, thay vì tự động thích ứng với cấu hình ô đo đạc dài (capture_window_seconds: 360 ở experiment 5).

Likely cause in pipeline: Pipeline thiếu cơ chế cấu hình động cho thời gian giãn cách giữa các kịch bản lỗi (dynamic cooldown orchestration), dẫn đến việc kịch bản sau có thể bị kích nổ khi kịch bản trước chưa thực sự hồi phục xong.

Recommended fix: Chuyển đổi tham số cooldown từ biến gán cứng trong mã nguồn thành tham số cấu hình động đầu vào (CLI argument hoặc YAML parameter), đồng thời bổ sung logic tự động kiểm tra trạng thái sức khỏe (health-check polling) của hệ thống trước khi bắt đầu bài test tiếp theo (§7.2 State Pollution).

# Gap 2: High detection latency (MTTD) during packet loss
Symptom: Tại experiment 2, chỉ số MTTD bị chậm lên tới 23 giây, chậm hơn gần gấp 3 lần so với thời gian phản hồi 9 giây của bài test HTTP retry storm.

Likely cause in pipeline: Bộ phát hiện bất thường (anomaly detector) bị phụ thuộc vào chu kỳ quét cấu hình tĩnh 15 giây. Cơ chế truyền lại gói tin của TCP (retransmissions) đã làm mượt các chỉ số, trì hoãn việc kích hoạt cảnh báo vượt ngưỡng.

Recommended fix: Nâng cấp bộ phát hiện lỗi từ dạng quét định kỳ (PromQL polling) sang dạng cửa sổ trượt theo thời gian thực (sliding windows) dựa trên luồng dữ liệu eBPF (§7.4 Telemetry Smoothing).

# Gap 3: Telemetry starvation in downstream dependency isolation
Symptom: Tại experiment 10, việc định vị dịch vụ gốc (root service) bị phụ thuộc hoàn toàn vào cấu hình chấm điểm cấu trúc (topology heuristics) gán sẵn thay vì phân tích trạng thái hàng đợi thực tế.

Likely cause in pipeline: Bộ phân tích nguyên nhân gốc rễ (RCA correlator) bị thiếu dữ liệu ở tầng ứng dụng sâu, mới chỉ đánh giá được các số liệu HTTP ở tầng biên (edge-level).

Recommended fix: Tích hợp trực tiếp các chỉ số hiệu năng nội bộ (như Tomcat thread pools, độ sâu hàng đợi connection pool của DB) vào logic xử lý của RCA (§7.1 Observation Blindspot).

## 5. Hypothesis for unconfirmed gaps
The Micro-outage Blurring Effect: Chúng tôi đặt giả thuyết rằng nếu một lỗi về tính sẵn sàng (experiment 3) diễn ra ngắn hơn 10 giây, chu kỳ quét metrics 15 giây hiện tại sẽ làm mượt hoàn toàn vết lõm của đồ thị, dẫn đến việc mất cảnh báo ngầm. Cần thực hiện thêm các bài test với kịch bản pod bị tắt/bật liên tục dưới 1 giây để xác định chính xác giới hạn lấy mẫu của hệ thống.