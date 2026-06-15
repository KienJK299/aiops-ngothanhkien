# W3-D1 Submission — <Điền Tên Bạn Vào Đây>

## 3 thứ tôi học được
1. **MƯMBR:** Hiểu rõ cách Prometheus phối hợp vế `and` giữa cửa sổ dài (Long Window - để kiểm tra lượng budget bị ngốn) và cửa sổ ngắn (Short Window - để xác định sự cố vẫn đang tiếp diễn) nhằm triệt tiêu hoàn toàn hiện tượng Alert rác khi lỗi đã kết thúc.
2. **Kỹ thuật đồng bộ hóa giữa Spec và Code Alert:** Học được cách bóc tách dữ liệu từ file phân tích tĩnh (`baseline.json`) để tính toán chính xác Error Budget thực tế cho chu kỳ 30 ngày (`total_events_per_month`, `allowed_failures_per_month`), từ đó đưa ra con số cấu hình Target thực tế (`0.97`) thay vì áp đặt các con số lý thuyết 99.9% một cách máy móc.
3. **Mối quan hệ đánh đổi (Trade-off) giữa Threshold và MTTD:** Hiểu sâu sắc rằng khi hạ thấp SLO Target (đồng nghĩa với việc tăng tỷ lệ lỗi cho phép), các hệ số Threshold mặc định (`14.4`) sẽ trở nên quá gắt, bắt buộc SRE phải chủ động hạ Threshold xuống (`0.6`) thì hệ thống mới có thể phát hiện lỗi nhanh dưới 60 giây.

## 1 thứ vẫn chưa rõ
Cách thiết lập hệ thống tự động hóa (Automation Workflow) để định kỳ chạy các script phân tích log thô (`baseline.json`), tự động tính toán lại và cập nhật các thông số SLO/Threshold vào GitOps repository khi sản phẩm có sự thay đổi lớn về mặt kiến trúc phần mềm hoặc quy mô traffic (Autotuning SLOs).

## 1 trade-off trong SLO decision của tôi mà tôi không chắc
Hạ Threshold của API Tier 1 từ mức tiêu chuẩn (`14.4`) xuống mốc `4.5` nhằm kéo thời gian phát hiện lỗi (`mttd_p50_s`) từ 360 giây xuống còn 60 giây để đạt KPI bài test.

## Validation report
"noise_reduction_pct": 25.0,
"mttd_delta_s": 60,
"rules_count": 2,
"verdict": "needs_review"

- Không thể đạt được mốc noise reduction >= 70 bởi vì ground truth quá ít dẫn đến việc chỉ với static_baseline cũng chỉ cho ra 1 false positive sau khi chạy qua custom mwmbr toàn bộ noise đã được lọc (1 noise) nên chỉ đạt đc 25%