import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor

# Cấu hình API URL
URL = "http://127.0.0.1:8000/incident"

# Dataset gồm 20 alert thật để test hiệu năng
payload = {
    "alerts": [
        {"id": f"a{i}", "ts": f"2026-06-12T10:00:{i:02d}Z", "service": "orders" if i%2==0 else "payment", "metric": "errors", "severity": 3}
        for i in range(20)
    ],
    "gap_sec": 49,
    "max_hop": 1
}

headers = {"Content-Type": "application/json"}

def send_request(_):
    try:
        start = time.time()
        response = requests.post(URL, json=payload, headers=headers, timeout=5)
        end = time.time()
        
        # Lấy latency từ Header do Server tính
        server_latency = float(response.headers.get("X-Response-Time-Ms", 0))
        # Tính tổng thời gian cả network (End-to-End)
        client_latency = (end - start) * 1000 
        
        return response.status_code, server_latency, client_latency
    except Exception as e:
        return 500, 0, 0

def run_benchmark():
    print("🚀 Đang chạy 20 request LIÊN TIẾP (Tuần tự)...")
    sequential_latencies = []
    for _ in range(20):
        status, server_lat, _ = send_request(0)
        if status == 200:
            sequential_latencies.append(server_lat)
    
    # Tính toán p50 và p99 cho chạy tuần tự
    sequential_latencies.sort()
    p50_seq = sequential_latencies[int(len(sequential_latencies) * 0.50)]
    p99_seq = sequential_latencies[int(len(sequential_latencies) * 0.95)] # phần tử gần cuối
    
    print(f"📊 Kết quả chạy tuần tự từ X-Response-Time-Ms:")
    print(f"   - p50 Latency: {p50_seq:.2f} ms")
    print(f"   - p99 Latency: {p99_seq:.2f} ms\n")

    print("🔥 Đang test CONCURRENCY (4 request đồng thời tổng 20 request)...")
    concurrent_latencies = []
    success_count = 0
    
    # Giả lập ab -n 20 -c 4 bằng ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(send_request, range(20)))
        
    for status, server_lat, client_lat in results:
        if status == 200:
            success_count += 1
            concurrent_latencies.append(client_lat) # Đo độ trễ client chịu đựng khi bị nghẽn
            
    concurrent_latencies.sort()
    p50_con = concurrent_latencies[int(len(concurrent_latencies) * 0.50)] if concurrent_latencies else 0
    p99_con = concurrent_latencies[int(len(concurrent_latencies) * 0.95)] if concurrent_latencies else 0

    print(f"📊 Kết quả khi có tải đồng thời (Concurrency c=4):")
    print(f"   - Số request thành công: {success_count}/20")
    print(f"   - Client p50 Latency: {p50_con:.2f} ms")
    print(f"   - Client p99 Latency: {p99_con:.2f} ms")

if __name__ == "__main__":
    # Cài thư viện requests nếu chưa có: pip install requests
    run_benchmark()