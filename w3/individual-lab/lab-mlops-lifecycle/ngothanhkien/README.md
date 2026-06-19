## 🚀 How to Run the Pipeline

Thực hiện theo các bước dưới đây để vận hành toàn bộ vòng đời MLOps:

# 1. **Khởi động hạ tầng**
Khởi chạy các dịch vụ nền tảng (MLflow, Prometheus, v.v.):
```
bash scripts/start_stack.sh
```
# 2. **Huấn luyện mô hình (v1)**

```
uv run python pipeline.py --data data/baseline.csv
```

# 3. **Khởi chạy Service phục vụ**
Bật API service để phục vụ dự đoán tại cổng 8000:

```
uv run python serve.py --port 8000
```

# 4. **Kiểm tra Drift**
Định kỳ chạy script để phát hiện sự phân kỳ dữ liệu giữa baseline và production:

```
uv run python drift_detector.py --reference data/baseline.csv --current data/drifted.csv --check-mode combined
```

# 5. **Tái huấn luyện tự động (Auto-Retraining)**
Nếu phát hiện drift, kích hoạt quy trình tái huấn luyện. Script này sẽ thực hiện sliding window training, đăng ký version v2 vào staging, thực hiện blue-green swap và tự động giám sát để rollback nếu cần thiết:

```
uv run python retrain.py \
  --reference data/baseline.csv \
  --current data/drifted.csv \
  --holdout data/holdout.csv \
  --post-deploy-eval data/post_deploy_eval.csv
```