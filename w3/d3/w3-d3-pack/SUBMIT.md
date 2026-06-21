## Outage chosen

* ID: 3
* Name: Cloudflare WAF regex
* Why this one: Em rất hứng thú với cách một Regex không tối ưu có thể làm nghẽn toàn bộ tài nguyên CPU của một hệ thống phân tán quy mô lớn. Việc tái hiện giúp hiểu sâu về cơ chế ReDoS (Regular Expression Denial of Service).
* Failure mode: catastrophic_backtracking

## 3 things I learned from this outage

1. Một thay đổi nhỏ trong rule hoặc cấu hình vẫn có thể gây ảnh hưởng trên phạm vi toàn hệ thống nếu được triển khai ở quy mô lớn.

2. CPU tăng cao chưa chắc xuất phát từ lưu lượng bất thường mà có thể do thuật toán hoặc logic xử lý bên trong ứng dụng.

3. Việc theo dõi metric là cần thiết nhưng chưa đủ, cần kết hợp log và thông tin deployment/change event để rút ngắn thời gian tìm nguyên nhân gốc.

## 1 thing my pipeline would still miss if this outage happened for real

* Pattern: Catastrophic backtracking do một regex mới được triển khai.
* Why miss: Pipeline hiện chỉ phân tích metric và log runtime, không theo dõi thay đổi cấu hình hoặc nội dung regex nên khó liên hệ CPU spike với một rule vừa được deploy.
* Mitigation idea: Bổ sung deployment events, config diff và correlation giữa change event với anomaly để hỗ trợ RCA.

## 1 decision in my ADR I'm not fully sure about

Việc sử dụng topology-aware RCA với trọng số cố định có thể chưa tối ưu trong mọi môi trường. Em chưa chắc cách lựa chọn trọng số giữa topology, thời gian xuất hiện anomaly và alert volume có thể tổng quát hóa cho các loại sự cố khác nhau.

## Cost model verdict for my stack (case 3 cost_model)

* ROI: 6.0
* Payback: 0.17 months
* Verdict: worth_it
