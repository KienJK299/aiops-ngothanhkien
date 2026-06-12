# EOD Checkpoint

## 1. Latency thực của Endpoint & Khả năng Scaling
Dựa trên thực nghiệm chạy 20 request liên tiếp tuần tự với dataset gồm 20 alert thật (chạy bằng file stress_test.py), các chỉ số độ trễ đo được từ header `X-Response-Time-Ms` của ứng dụng như sau:
* **p50 Latency:** **3.03 ms** 
* **p99 Latency:** **6.00 ms**

### Phân tích các Phase xử lý:  
* **Phase chiếm phần lớn thời gian:** Phase **Correlate** (duyệt đồ thị tìm đường đi ngắn nhất thông qua `networkx`) và Phase **RCA** (tính toán toán học ma trận cho thuật toán PageRank) chiếm khoảng **75% - 80%** tổng thời gian xử lý tại server. Các tầng Validate (Pydantic) và Serialize dữ liệu đầu ra chạy trên nền mã C mã hóa tối ưu nên tiêu tốn thời gian rất nhỏ (< 1ms).
* **Khả năng Scaling khi Input tăng gấp 10×:**
    * **Scale Linear / Super-Linear:** Phase **Correlate** và **RCA** sẽ tăng tiến tuyến tính hoặc lũy thừa theo kích thước dữ liệu. Khi số lượng alert tăng lên 10 lần, số lượng đỉnh ($V_{sub}$) và cạnh ($E_{sub}$) trong đồ thị con cần trích xuất tăng lên, khiến chi phí duyệt BFS tìm đường ngắn nhất và số vòng lặp hội tụ của thuật toán PageRank phình to rõ rệt.
    * **Fixed Cost:** Phase khởi tạo cấu trúc lớp Pydantic Schema có chi phí cố định tương đối ổn định ban đầu, mặc dù thời gian lặp kiểm tra tính hợp lệ của mảng JSON vẫn sẽ tăng nhẹ theo độ dài danh sách.

---

## 2. Concurrency Test & Cơ chế Fallback
Kết quả kiểm thử tải đồng thời (giả lập thông qua `ThreadPoolExecutor` trên Windows với cấu hình 4 request gửi đồng thời, tổng cộng 20 request) cho thấy:
* **Tỷ lệ thành công:** **20/20 request**
* **Client p50 Latency:** **22.00 ms**
* **Client p99 Latency:** **49.39 ms**

### Đánh giá Bottleneck & Hành vi hệ thống:
* **Bottleneck đầu tiên quan sát được:** Nút thắt nằm ở **CPU-bound tại Event Loop**. Vì cấu hình chạy Single Worker (`--workers 1`), tiến trình Python bị ràng buộc bởi cơ chế **GIL (Global Interpreter Lock)**. Khi các phép toán đồ thị nặng của `networkx` chiếm dụng CPU, nó sẽ block nhẹ luồng thực thi của Event Loop, làm cho các request gửi đồng thời phải xếp hàng chờ đợi luân phiên ở tầng Network, dẫn đến việc độ trễ phía Client (`22ms` - `49.39ms`) cao hơn rõ rệt so với thời gian xử lý thuần tại Server (`3ms`).
* **Cơ chế Fallback Path:** Hệ thống có tích hợp sẵn đường dẫn dự phòng Heuristic (Fallback Rule). Khi dữ liệu cảnh báo mới không khớp với bất kỳ kịch bản sự cố nào cũ trong tri thức lịch sử (`incidents_history.json`), hệ thống tự động gán `root_cause_class = "unknown"` và trả về tập hành động khắc phục chung mặc định: `["Investigate logs manually", "Check system metrics"]`.

---

## 3. Thiết kế Healthz & Readyz Endpoints
* **`/healthz`:** Trả về `{"status": "ok"}`
* **`/readyz`:** Trả về `{"status":"ready"}`

### Lý do tách biệt thay vì gộp làm một:
Trong môi trường Production (như Kubernetes hoặc ECS), khi container vừa mới khởi động, nó cần một khoảng thời gian (Warm-up) để nạp các file dữ liệu cấu hình cồng kềnh (ví dụ: file đồ thị JSON nặng). 
* Nếu gộp chung, điều hướng traffic vào quá sớm khi dữ liệu chưa lên RAM sẽ gây ra lỗi hàng loạt cho người dùng. 
* Nếu dùng chung một endpoint lỗi cho liveness, hệ thống điều phối sẽ lầm tưởng ứng dụng bị treo và liên tục hạ tải/khởi động lại (Restart Loop) tiến trình một cách vô ích. Việc tách biệt giúp hệ thống biết ứng dụng vẫn sống bình thường (`/healthz` Pass) nhưng sẽ chặn không cho luồng traffic người dùng đổ vào cho đến khi dữ liệu nạp xong (`/readyz` Pass).

### Trạng thái khi LLM API Down:
Khi LLM API Down, endpoint `/readyz` của hệ thống **VẪN PASS**, vì hệ thống được thiết kế theo kiến trúc giảm cấp chịu lỗi (Graceful Degradation). Core logic tính toán phân tích nguyên nhân gốc rễ (RCA) dựa trên thuật toán đồ thị nội bộ PageRank và tập đối sánh quy tắc Heuristic chạy offline hoàn toàn trên RAM. Sự cố sập API của nhà cung cấp LLM chỉ làm giảm độ sâu giải thích ngữ nghĩa, chứ không làm tê liệt khả năng xử lý cốt lõi của API, do đó hệ thống vẫn đủ điều kiện nhận tải tốt.