# Bạn chọn gap_sec bao nhiêu, vì sao?

- gap_sec = 49s được chọn bằng cách sử dụng kỹ thuật 95th Percentile trên phân phối intra-incident gap

- Nếu chọn gap_sec quá nhỏ như 30s, incident dài dễ bị bị xé nhỏ thành nhiều cluster độc lập. Còn nếu chọn gap_sec quá lớn như 600+ thì hệ thống dễ bắt các alerts trong các incident không liên quan, gây false correlation

# Bạn chọn max_hop bao nhiêu, vì sao?

max_hop hiện tại được set = 1 do khi quan sát mối liên hệ giữa các service, nếu như max_hop là 2 thì thuật toán trở nên quá bao quát, cover hơn 50% tổng số path trong graph, set max_hop = 1 sẽ đảm bảo tính chính xác cao hơn

# 1 alert ID đã bị “miss” (không match cluster nào) — tại sao?

1 alert ID đã bị miss đó là `a-0013` vì nó không có mối quan hệ correlation trực tiếp đến các service khác nó chỉ đơn giản là ngẫu nhiên xảy ra trong khoảng thời gian gap_sec


# Nếu có 10000 alert thay vì 20, code của bạn sẽ chậm ở đâu?
Với 10.000 alerts, code sẽ bị nghẽn tại hàm topology_group. Do sử dụng nested loops để so sánh cặp service (với độ phức tạp $O(S^2)$, trong đó $S$ là số lượng service duy nhất) kết hợp với việc gọi hàm nx.shortest_path_length bên trong vòng lặp, tổng thời gian thực thi sẽ tăng theo hàm mũ khi số lượng service tăng lên, gây ra hiện tượng treo tiến trình.

# EOD Checkpoint
## Vì sao fingerprint cho dedup không include timestamp hay value? Cho ví dụ nếu include thì hệ thống behave ra sao.

Fingerprint được tạo thành từ các field cố định nhằm định danh cho từng loại alert, còn timestamp và value lại biến đổi liên tục theo thời gian nên những field như vậy không được cho vào fingerprint. 
Nếu tích hợp hai field này vào fingerprint, hệ thống sẽ sinh ra vô số mã định danh duy nhất tương ứng với mỗi một timestamp hay một value. Điều này làm mất đi bản chất của fingerprint là dedup các alert có cùng nguyên nhân để ngăn chặn tình trạng bão alert

## Sự khác biệt giữa “duplicate” và “correlated” alert là gì? Ví dụ cụ thể từ lab dataset.

### Duplicate là 1 sự cố lặp đi lặp lại trong 1 khoảng thời gian vd:
```json
{"id": "a-0002", "ts": "2026-06-12T09:42:18Z", "service": "payment-svc", "metric": "db_connection_pool_used_ratio", "severity": "crit",  "value": 0.99, "threshold": 0.95, "labels": {"env": "prod", "region": "ap-southeast-1"}}
{"id": "a-0011", "ts": "2026-06-12T09:44:02Z", "service": "payment-svc", "metric": "db_connection_pool_used_ratio", "severity": "crit",  "value": 1.00, "threshold": 0.95, "labels": {"env": "prod", "region": "ap-southeast-1"}}
```

--> cùng là 1 payment-svc 

### Correlated là 1 sự cố này kéo theo 1 sự cố khác vd:

```json
{"id": "a-0004", "ts": "2026-06-12T09:42:30Z", "service": "payment-svc", "metric": "error_rate",                    "severity": "warn",  "value": 0.04, "threshold": 0.02, "labels": {"env": "prod", "region": "ap-southeast-1"}}
{"id": "a-0005", "ts": "2026-06-12T09:42:45Z", "service": "checkout-svc","metric": "latency_p99_ms",                "severity": "warn",  "value": 2100, "threshold": 1500, "labels": {"env": "prod", "region": "ap-southeast-1"}}

```

--> payment-svc kéo theo checkout-svc

## gap_sec = 30 (rất ngắn) vs gap_sec = 600 (rất dài) — mỗi cái sẽ ảnh hưởng output thế nào? 1 dòng cho mỗi case.

gap_sec = 30 sẽ gây phân mảnh, một sự cố kéo dài sẽ bị xé nhỏ thành nhiều cluster độc lập vì các alert chỉ cách nhau hơn 30 giây không được gom lại


gap_sec = 600 sẽ gây gom nhầm các alert hoàn toàn ko liên quan bỗng dưng bị gộp chung vào một cluster chỉ vì chúng vô tình xảy ra cách nhau trong khoảng 10 phút.

## Trong scenario chính (payment-svc pool exhaustion), recommender-svc cũng alert (batch retrain). Correlator của bạn có gom recommender vào cluster chính không? Vì sao có / không?

Recommender không được đưa vào cluster chính vì khi set max_hop = 1, recommender không có liên hệ trực tiếp đến các service khác nên nó không có correlation với nhau.

## Limitation lớn nhất của topology grouping mà bạn nhận ra? Suggest 1 cách khắc phục.

Theo cách làm hiện tại thì việc tách các groups được thực hiện bằng cách dedup, session với gap_sec = 49 sau đó gom các alert theo cấu trúc servcie (dựa vào service graph) nằm trog khoảng max_hop thì sẽ được giữ lại cluster nếu không nó sẽ tạo 1 cluster mới

Vấn đề hiện tại là đôi lúc những alert noise ngẫu nhiên nằm trong phạm vi gap_sec và edge đó thì phương pháp này hoàn toàn không thể cô lập được

Suggest cách khắc phục: Implement thêm một layer về semantic similarity giữa các alert thay vì chỉ dựa vào fingerprint chính xác. Approach đơn giản là dùng Jaccard similarity trên các token của metric name, điển hình như tách db_connection_pool_used_ratio thành các từ db, connection, pool, used, ratio, rồi so similarity giữa các alert. Nếu similarity threshold (ví dụ 0.9), thì coi như 2 alert có quan hệ về mặt semantic 