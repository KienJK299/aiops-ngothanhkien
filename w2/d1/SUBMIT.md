# Vì sao fingerprint cho dedup không include timestamp hay value? Cho ví dụ nếu include thì hệ thống behave ra sao.

Fingerprint được tạo thành từ các field cố định nhằm định danh cho từng loại alert, còn timestamp và value lại biến đổi liên tục theo thời gian nên những field như vậy không được cho vào fingerprint. 
Nếu tích hợp hai field này vào fingerprint, hệ thống sẽ sinh ra vô số mã định danh duy nhất tương ứng với mỗi một timestamp hay một value. Điều này làm mất đi hoàn toàn bản chất của fingerprint là dedup các alert có cùng nguyên nhân để ngăn chặn tình trạng bão alert

# Sự khác biệt giữa “duplicate” và “correlated” alert là gì? Ví dụ cụ thể từ lab dataset.

## Duplicate là 1 sự cố lặp đi lặp lại trong 1 khoảng thời gian vd:
{"id": "a-0002", "ts": "2026-06-12T09:42:18Z", "service": "payment-svc", "metric": "db_connection_pool_used_ratio", "severity": "crit",  "value": 0.99, "threshold": 0.95, "labels": {"env": "prod", "region": "ap-southeast-1"}}
{"id": "a-0011", "ts": "2026-06-12T09:44:02Z", "service": "payment-svc", "metric": "db_connection_pool_used_ratio", "severity": "crit",  "value": 1.00, "threshold": 0.95, "labels": {"env": "prod", "region": "ap-southeast-1"}}
```

--> cùng là 1 payment-svc 

## Correlated là 1 sự cố này kéo theo 1 sự cố khác vd:

```json
{"id": "a-0004", "ts": "2026-06-12T09:42:30Z", "service": "payment-svc", "metric": "error_rate",                    "severity": "warn",  "value": 0.04, "threshold": 0.02, "labels": {"env": "prod", "region": "ap-southeast-1"}}
{"id": "a-0005", "ts": "2026-06-12T09:42:45Z", "service": "checkout-svc","metric": "latency_p99_ms",                "severity": "warn",  "value": 2100, "threshold": 1500, "labels": {"env": "prod", "region": "ap-southeast-1"}}

```

--> payment-svc kéo theo checkout-svc

# gap_sec = 30 (rất ngắn) vs gap_sec = 600 (rất dài) — mỗi cái sẽ ảnh hưởng output thế nào? 1 dòng cho mỗi case.

gap_sec = 30 sẽ gây phân mảnh, một sự cố kéo dài sẽ bị xé nhỏ thành nhiều cluster độc lập vì các alert chỉ cách nhau hơn 30 giây không được gom lại


gap_sec = 600 sẽ gây gom nhầm các alert hoàn toàn vô can bỗng dưng bị gộp chung vào một cluster chỉ vì chúng vô tình xảy ra cách nhau trong khoảng 10 phút.

# Trong scenario chính (payment-svc pool exhaustion), recommender-svc cũng alert (batch retrain). Correlator của bạn có gom recommender vào cluster chính không? Vì sao có / không?

Recommender không được đưa vào cluster chính vì khi set max_hop = 1, recommender không có liên hệ trực tiếp đến các service khác nên nó không có correlation với nhau.

# Limitation lớn nhất của topology grouping mà bạn nhận ra? Suggest 1 cách khắc phục.

Hiện tại khi xét grouping đầu tiên nó sẽ gom hết tất cả các alert cách nhau 1 khoảng là gap_sec sau đó tiến hành check nếu như số edge nằm trog khoảng max_hop thì sẽ được giữ lại cluster nếu không nó sẽ tạo 1 cluster mới.

Vấn đề hiện tại là đôi lúc những alert noise ngẫu nhiên nằm trong phạm vi gap_sec và edge đó thì phương pháp này hoàn toàn không thể cô lập được