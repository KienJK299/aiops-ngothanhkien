# AIOps Mini-Platform Spec — ngothanhkien

## 1. Platform overview

Hệ thống AIOps được xây dựng để giám sát ứng dụng thương mại điện tử dạng microservice gồm frontend, cart-service và payment-service.

Metric được thu thập bằng Prometheus, log được lưu dưới dạng JSONL. Nền tảng cung cấp khả năng phát hiện bất thường, correlation và root cause analysis phục vụ DevOps và SRE.

---

## 2. SLO definition (from W3-D1)

### frontend

SLI:
Availability

SLO:
99.9%

Error budget:
0.1%

### cart-service

SLI:
P95 latency

SLO:
P95 < 300 ms

Error budget:
5%

### payment-service

SLI:
Error rate

SLO:
Error rate < 1%

Error budget:
1%

---

## 3. Detection + Correlation + RCA stack (from W1+W2)

### Detection

Do dữ liệu metric có phân phối lệch nên nhóm sử dụng IQR kết hợp Isolation Forest để phát hiện anomaly.

### Correlation

Các anomaly xảy ra gần nhau về mặt thời gian sẽ được gom vào cùng một incident. Log và metric được đồng bộ theo timestamp.

### RCA

RCA sử dụng phương pháp topology-aware theo ADR-001, kết hợp topology graph, thời điểm xuất hiện anomaly đầu tiên và số lượng alert.

---

## 4. Reliability validation (from W3-D2)

Chaos engineering được sử dụng để tái hiện lỗi dependency timeout.

Ba khoảng trống lớn nhất:

1. False positive khi chỉ có anomaly đơn lẻ.
2. RCA xác định sai root cause trong retry storm.
3. Chưa có trace nên khó suy luận nhân quả.

---

## 5. Operational pattern (from W3-D3)

Nhóm tái hiện sự cố dependency timeout gây retry storm.

Bài học rút ra:

* Alert volume không phản ánh root cause.
* Topology graph giúp cải thiện RCA.
* Metric đơn thuần chưa đủ để suy luận nguyên nhân.

ADR-001 được đưa ra để giải quyết vấn đề này.

---

# 6. Cost model (from W3-D3)

Mô hình chi phí được sử dụng để đánh giá giá trị kinh doanh của nền tảng AIOps thông qua khả năng giảm MTTR (Mean Time To Recovery).

Kết quả chạy cost_model.py cho ba kịch bản:

Scenario 1 – Hệ thống nhỏ (20 services)
{
'monthly_value': 8000.0,
'monthly_cost': 15000,
'roi': 0.5333333333333333,
'payback_months': 1.875,
'verdict': 'not_worth_it'
}

ROI < 1 nên việc đầu tư AIOps trong trường hợp này chưa mang lại hiệu quả kinh tế.

Scenario 2 – Hệ thống quy mô trung bình (100 services)
{
'monthly_value': 80000.0,
'monthly_cost': 25000,
'roi': 3.2,
'payback_months': 0.3125,
'verdict': 'worth_it'
}

ROI đạt 3.2 và thời gian hoàn vốn khoảng 0.31 tháng, cho thấy AIOps đem lại giá trị đáng kể.

Scenario 3 – Hệ thống thương mại điện tử (50 services)
{
'monthly_value': 120000.0,
'monthly_cost': 20000,
'roi': 6.0,
'payback_months': 0.16666666666666666,
'verdict': 'worth_it'
}

Đối với hệ thống hiện tại, kịch bản thứ ba được xem là gần với thực tế nhất. Với ROI = 6.0 và thời gian hoàn vốn khoảng 0.17 tháng, nền tảng AIOps được đánh giá là worth_it.

Break-even point đạt được khi giá trị tiết kiệm hàng tháng vượt quá chi phí vận hành 20,000 USD/tháng.
---

## 7. Open risks

| Rủi ro                   | Mức độ     | Hướng khắc phục        |
| ------------------------ | ---------- | ---------------------- |
| Chưa có trace            | Cao        | Tích hợp OpenTelemetry |
| Drift của detector       | Trung bình | Retrain định kỳ        |
| Topology graph lỗi thời  | Trung bình | Tự động discovery      |
| False positive           | Trung bình | Temporal aggregation   |
| Trọng số RCA chưa tối ưu | Thấp       | Adaptive weighting     |
