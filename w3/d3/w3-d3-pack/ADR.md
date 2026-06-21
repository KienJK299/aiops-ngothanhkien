# ADR-001: Sử dụng RCA nhận thức topology thay cho count-based ranking

## Status

Accepted

## Context

Trong quá trình chaos testing, pipeline RCA xác định sai root cause do sử dụng số lượng alert làm tiêu chí chính. Khi xảy ra cascading failure, các service downstream retry liên tục và sinh ra nhiều alert hơn service upstream thực sự gây lỗi.

Do đó phương pháp count-based ranking không đáng tin cậy trong các sự cố lan truyền.

## Decision

RCA sẽ kết hợp ba tín hiệu:

1. Vị trí trong topology (ưu tiên service upstream).
2. Thời điểm xuất hiện anomaly đầu tiên.
3. Số lượng alert (chỉ dùng để phân xử khi hai tín hiệu trên tương đương).

Service có điểm tổng hợp cao nhất sẽ được xem là root cause.

## Alternatives considered

### Alternative 1: Count-based ranking

#### Ưu điểm

* Đơn giản.
* Chi phí tính toán thấp.
* Dễ giải thích.

#### Nhược điểm

* Dễ xác định sai root cause khi xảy ra retry storm.
* Downstream service có thể tạo nhiều alert hơn upstream service.

Kết luận: Rejected.

---

### Alternative 2: Graph PageRank

#### Ưu điểm

* Khai thác dependency graph.
* Có khả năng mô hình hóa sự lan truyền lỗi.

#### Nhược điểm

* Không xét yếu tố thời gian.
* Không phân biệt được service nào lỗi trước.

Kết luận: Rejected as standalone.

---

### Alternative 3: LLM-only RCA

#### Ưu điểm

* Linh hoạt.
* Có khả năng phân tích log.

#### Nhược điểm

* Có nguy cơ hallucination.
* Kết quả không ổn định.
* Chi phí suy luận cao.

Kết luận: Không dùng làm phương pháp chính.

## Consequences

### Tích cực

* Xác định đúng root cause trong các sự cố lan truyền.
* Nếu thiếu một loại dữ liệu, các tín hiệu còn lại vẫn hoạt động.

### Trade-off

* Tốn thêm tài nguyên tính toán.
* Cần duy trì topology graph luôn được cập nhật.
* Trọng số giữa các tín hiệu cần được hiệu chỉnh theo từng môi trường.
