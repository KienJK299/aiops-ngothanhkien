# W3-D2 Submission — ngothanhkien
## 3 things I learned about my AIOps pipeline
Sự khác biệt giữa Symptom và Root Cause: Hệ thống chứng minh khả năng phân tách rất tốt nhờ bộ chấm điểm cấu trúc (topology scoring). Điển hình ở experiment 10 (Retry Storm), dù checkout-svc liên tục báo lỗi HTTP 500 do nghẽn cổ chai, pipeline vẫn tỉnh táo đánh dấu nó là "đứa hứng triệu chứng" (symptom carrier) và tìm ra thủ phạm thực sự phía sau là payment-svc.

Độ trễ truyền tin của giao thức (Protocol Latency Masking): Trong các bài test lỗi mạng tầng thấp như experiment 2 (Packet Loss), thời gian phát hiện (MTTD = 23s) bị kéo dài đáng kể so với lỗi tầng ứng dụng. Lý do là vì cơ chế tự động thử lại của TCP đã tạm thời che giấu sự sụt giảm metric trong vài chu kỳ đầu tiên trước khi chạm ngưỡng cảnh báo.

Tầm quan trọng của dữ liệu Meta-Monitoring: Việc giám sát hệ thống thu thập log (experiment 7 - Disk Fill) cho thấy một hệ thống AIOps chuẩn cần có các kênh metric độc lập cho phần metadata plane. Nhờ vậy, khi hệ thống log-collector bị cạn kiệt đĩa cứng, pipeline vẫn bắt được tín hiệu cảnh báo nạp log trễ mà không gây ảnh hưởng hay làm gián đoạn luồng dữ liệu giao dịch core của người dùng.

## 1 fault I expected the pipeline to catch but it missed
Experiment: exp 3 (inventory_pod_kill) trong trường hợp thời gian lỗi diễn ra cực ngắn (Micro-outage).

Why I expected detection: Khi một container/pod của dịch vụ lõi như inventory-svc bị kill liên tục, hệ thống giám sát hạ tầng (cadvisor/Docker daemon) phải lập tức nhận biết được sự thay đổi trạng thái vòng đời (Eviction/Termination) để kích hoạt cảnh báo sụt giảm tính sẵn sàng.

Why the pipeline missed (hypothesis): Trở ngại nằm ở Telemetry Smoothing. Hiện tại Prometheus đang cấu hình scrape_interval: 15s. Nếu hành động pod_kill hoặc lỗi sụt giảm xảy ra và tự phục hồi nhanh chóng trong vòng dưới 10 giây, thuật toán PromQL định kỳ sẽ vô tình "làm mượt" đồ thị (averaged out), khiến chỉ số sụt giảm không đủ sâu để vượt qua ngưỡng tĩnh (static threshold) và lỗi sẽ bị trượt ngầm hoàn toàn.

## 1 trade-off in pipeline design I want to rethink
Đánh đổi giữa Tốc độ kiểm thử (Testing Velocity) và Độ sạch của dữ liệu (State Pollution): - Chi tiết: Trong bài Lab này, chúng ta đã chủ động can thiệp mã nguồn để hạ thời gian nghỉ giữa các bài test xuống mức tối thiểu (COOLDOWN_SECONDS = 5) nhằm tối ưu tốc độ chạy script kiểm thử local. Tuy nhiên, sự đánh đổi lại cực kỳ rủi ro nếu áp dụng cấu hình này lên hệ thống production thật. Khoảng thời gian 5 giây là quá ngắn, không đủ để microservices giải phóng hoàn toàn các kết nối TCP bị nghẽn, xả sạch RAM hoặc đưa đồ thị metric về trạng thái phẳng lặng ban đầu (Steady-state). Sự "nhiễm độc dữ liệu" từ bài test trước sang bài test sau sẽ làm mù bộ tương quan RCA.

## Scoreboard summary
- detected: 10/10
- rca_correct: 10/10
- mttd_p50: 19s
- false_alarms: 0
- verdict: PASS