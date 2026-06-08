# Detection Approach — DESIGN.md

## Approach
Stateful Streaming Anomaly Detection using:
- Sliding Window (local baseline)
- EWMA (Exponential Weighted Moving Average)
- Threshold + Persistence Check
- State Machine (anti-alert-spam)

---

## Tại sao chọn approach này

Streaming data có đặc điểm:
- Noise (dao động nhỏ liên tục)
- Có spike ngắn (không phải anomaly thật)
- Không có toàn bộ history (chỉ thấy từng tick)

Vì vậy:

- Sliding window -> tạo baseline cục bộ (local context)
- EWMA -> làm mượt dữ liệu, giảm nhiễu
- Persistence check -> đảm bảo anomaly là “sustained”, không phải spike
- Stateful detection -> tránh spam alert mỗi tick

- Approach này cân bằng giữa:
- Độ chính xác (ít false positive)
- Tốc độ phát hiện (low TTD)
- Đơn giản (phù hợp lab 3h)

---

## Cách hoạt động

Pipeline xử lý từng event theo streaming:

### Mỗi tick:
1. Nhận metrics + logs
2. Update sliding window (deque)
3. Update EWMA cho các metric quan trọng
4. Kiểm tra anomaly condition
5. Nếu có anomaly:
   - Chỉ alert khi chuyển trạng thái (NORMAL → ANOMALY)

---

## Core Techniques

### 1. Sliding Window
Lưu N giá trị gần nhất để:
- Tính baseline (average)
- Kiểm tra persistence (liên tục N điểm bất thường)

---

### 2. EWMA (Smoothing)

EWMA giúp giảm noise:

ewma = α * current + (1 - α) * previous

- α = 0.3 (ưu tiên dữ liệu mới nhưng vẫn giữ trend)
- Dùng cho:
  - timeout_rate
  - error_rate
  - request rate (RPS)

---

### 3. Persistence Check

Không trigger anomaly nếu chỉ là spike ngắn.

Ví dụ:
- 3 điểm cuối liên tiếp đều vượt threshold

==> đảm bảo anomaly là thật (sustained issue)

---

### 4. Stateful Detection (Quan trọng nhất)

Mỗi loại anomaly có state:

- NORMAL
- ANOMALY

Chỉ fire alert khi:
- NORMAL -> ANOMALY

==> Tránh spam alert mỗi tick

---

## Logic phát hiện anomaly

### 1. Dependency Timeout (quan trọng nhất)

Điều kiện:

- EWMA(timeout_rate) > 0.3
- EWMA(error_rate) > 0.5
- Persistence: 3 ticks liên tiếp đều cao

==> dấu hiệu downstream service bị lỗi nặng

---

### 2. Traffic Spike

Điều kiện:

- RPS > 1.5 * average(window)
- Latency tăng cao (>100ms)
- Persistence: >= 3 ticks

==> traffic tăng gây degrade hệ thống

---

### 3. Memory Leak

Điều kiện:

- Memory utilization > 80%
- Memory tăng liên tục 

==> dấu hiệu leak hoặc GC issue

---

### 4. Log-based Signal (phụ)

- Ít nhất 2 ERROR/FATAL logs trong cùng tick

==> dùng làm tín hiệu bổ sung (weak signal)

---

## Parameters

| Parameter | Value | Lý do |
|----------|------|------|
| window size | 10 | phản ứng nhanh hơn, đủ để smoothing |
| EWMA alpha | 0.3 | cân bằng giữa noise và responsiveness |
| persistence | 3 ticks | tránh spike giả |
| timeout_rate | > 0.3 | vượt xa baseline (0–0.4) |
| error_rate | > 0.5 | hệ thống đang fail rõ ràng |
| RPS spike | > 1.5x avg | phân biệt spike thật |
| latency | > 100ms | cao hơn nhiều so với baseline |

---

## Cải thiện nếu có thêm thời gian

- Hybrid EWMA + Z-score (adaptive threshold)
- Multivariate detection (correlation giữa metrics)
- Root cause analysis (phân biệt CPU vs dependency vs traffic)
- Dynamic threshold theo time-of-day (seasonality)
- Alert grouping & deduplication nâng cao