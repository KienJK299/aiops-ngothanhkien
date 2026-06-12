# System Design Documentation:

## 1. Pipeline Architecture trong Endpoint
Hệ thống xử lý sự cố (Incident RCA Pipeline) tuân thủ kiến trúc luồng tuần tự qua các giai đoạn độc lập nhằm biến đổi dữ liệu cảnh báo thô thành kết quả phân tích có cấu trúc:
* **Data Validation Layer (Pydantic):** Endpoint `/incident` tiếp nhận Payload, tự động ép kiểu và kiểm tra cấu trúc danh sách cảnh báo qua `IncidentRequest` schema. Nếu dữ liệu sai định dạng, hệ thống chặn đứng và trả về lỗi `422 Unprocessable Entity` thay vì lỗi `500`.
* **Correlation Engine (Heuristic Clustering):** * *Gom cụm theo thời gian (Temporal):* Sắp xếp các alert theo mốc `ts` và nhóm chúng lại nếu khoảng cách tuyến tính $\le$ `gap_sec`.
    * *Lí do chọn gap_sec = 49 và max_hop = 1:* 
        * `gap_sec` = `49s` được chọn bằng cách sử dụng kỹ thuật 95th Percentile trên phân phối intra-incident gap.
        * `max_hop` hiện tại được set = `1` do khi quan sát mối liên hệ giữa các service, nếu như `max_hop` là `2` thì thuật toán trở nên quá bao quát, cover hơn `50%` tổng số path trong graph, set `max_hop` = `1` sẽ đảm bảo tính chính xác cao hơn
    * *Gom cụm theo kiến trúc (Topology):* Dựa trên đồ thị vô hướng (`GLOBAL_GRAPH.to_undirected()`), thuật toán duyệt tìm đường đi ngắn nhất giữa các dịch vụ. Dịch vụ nào có khoảng cách $\le$ `max_hop` sẽ được gom chung vào một `cluster_id`.
* **RCA & Heuristic Inference Engine:** Với mỗi cụm, một đồ thị con (Subgraph) được trích xuất. Hệ thống áp dụng thuật toán **PageRank** ($d=0.85$) kết hợp trọng số thời gian xuất hiện alert đầu tiên (`t_score`) để tính điểm ưu tiên và phân định dịch vụ nguyên nhân gốc rễ (`root_cause`).
* **Knowledge-Base Matching Layer (kNN Fallback):** Đối soát tập dịch vụ bị ảnh hưởng với lịch sử sự cố qua `incidents_history.json`. Nếu độ tương đồng đạt ngưỡng, hệ thống kế thừa `root_cause_class` và `remediation`. Nếu không, cơ chế Fallback tự động gán nhãn `"unknown"` kèm hành động điều tra thủ công.

---

## 2. Latency Budget Breakdown
Để đảm bảo API hoạt động trong kịch bản thời gian thực, ngân sách độ trễ (Latency Budget) được phân bổ nghiêm ngặt dưới **15ms** cho tổng chu kỳ xử lý tại tầng Application:

| Giai đoạn xử lý (Component) | Latency Budget | Phương pháp tối ưu |
| :--- | :---: | :--- |
| **I/O & Validation Layer** | < 1.5ms | Parse JSON bằng Pydantic (C-based speed), toàn bộ dữ liệu Topology Graph và Lịch sử sự cố được nạp sẵn vào RAM (`InMemory Cache`) tại sự kiện `startup`. Không có I/O block lúc runtime. |
| **Correlation & Graph Traversal** | < 5.0ms | Chuyển đổi đồ thị NetworkX sang dạng vô hướng một lần cho mỗi cụm, giới hạn không gian duyệt nhờ thuật toán cắt tỉa đồ thị con dựa theo `max_hop`. |
| **RCA Score Calculation** | < 4.0ms | Thuật toán PageRank chỉ chạy trên subgraph cực nhỏ (chỉ chứa các service có alert), giảm độ phức tạp tính toán từ $O(N^2)$ xuống $O(V_{sub} + E_{sub})$. |
| **Serialization & Middleware** | < 1.5ms | Định dạng dữ liệu trả về và tính toán `X-Response-Time-Ms` thông qua ASGI Middleware bất đồng bộ. |
| **Tổng ngân sách dự phòng** | **< 12.0ms** | *Thực tế vận hành local đạt ~3.99ms - 4.15ms.* |

---

## 3. Production Concern: Concurrency Handling
Do đặc thù bài toán yêu cầu chạy server ở dạng **Single Process / Single Worker** (`--workers 1`), năng lực xử lý đồng thời (Concurrency) trở thành rủi ro lớn nhất nếu gặp tình trạng Thread Blocking khi nhiều client gọi API cùng lúc.

### Giải pháp xử lý trong mã nguồn:
1.  **Asynchronous Endpoint (`async def`):** Endpoint `/incident` được định nghĩa dưới dạng hàm bất đồng bộ (`async def`). Khi FastAPI nhận request, nó giải phóng Event Loop tại các điểm chờ I/O, cho phép nhận liên tục các kết nối TCP mới mà không bắt request sau phải chờ request trước xếp hàng (Non-blocking I/O).
2.  **Bypass CPU-bound operations:** Hệ thống cung cấp biến môi trường `AIOPS_USE_LLM=false`. Khi chạy tải cao hoặc benchmark, các tác vụ suy luận AI nặng nề (nếu có) sẽ bị ngắt hoàn toàn, chuyển hướng sang Heuristic thuần túy chạy bằng CPU giúp giải phóng tài nguyên tính toán ngay lập tức.
3.  **In-Memory Graph Lookup:** Tuyệt đối không đọc file `services.json` hay `incidents_history.json` lúc nhận request. Mọi thao tác truy vấn cấu trúc dữ liệu đồ thị đều diễn ra trên RAM với độ phức tạp $O(1)$ hoặc $O(V)$, triệt tiêu trạng thái nghẽn tiến trình do nghẽn ổ đĩa (Disk I/O Bottleneck).

---

## 4. Trade-off: Vì sao chọn FastAPI?

### Thay vì Flask:
* **Tốc độ & Hiệu năng:** Flask dựa trên WSGI (đồng bộ), mỗi worker chỉ xử lý một request tại một thời điểm. FastAPI dựa trên ASGI (bất đồng bộ), tối ưu hóa kiến trúc Event Loop giúp xử lý hàng ngàn request đồng thời trên một worker duy nhất, phù hợp hoàn hảo với ràng buộc `--workers 1` của bài toán.
* **Data Validation:** Flask yêu cầu code thủ công hoặc cài thêm `marshmallow` để validate JSON đầu vào. FastAPI tích hợp sẵn `Pydantic`, tự động hóa việc lọc dữ liệu lỗi và sinh tài liệu Swagger UI tự động giúp đẩy nhanh tốc độ kiểm thử.

### Thay vì BentoML:
* **Trọng lượng hệ thống:** BentoML là một framework quá nặng, được thiết kế chuyên biệt để đóng gói mô hình ML như PyTorch/TensorFlow và tối ưu hóa việc gom cụm micro-batching. 
* **Tính phù hợp:** Pipeline hiện tại của hệ thống bản chất là sự kết hợp giữa xử lý logic đồ thị cấu trúc (Graph Theory) và đối sánh luật (Heuristic rules). Sử dụng BentoML sẽ làm tăng dung lượng container image lên hàng GB và tiêu tốn tài nguyên RAM vô ích, trong khi FastAPI giữ cho ứng dụng cực kỳ nhẹ (~50MB package dependencies), khởi động instant dưới 1 giây và phản hồi với độ trễ thấp hơn rõ rệt.