import pandas as pd
import queue
import time
import threading

CSV_PATH = "Data/machine_temperature_system_failure.csv"
q = queue.Queue()

def producer():
    df = pd.read_csv(CSV_PATH)
    for _, row in df.iterrows():
        q.put(row.to_dict())
        # time.sleep(0.01) # Giả lập tốc độ stream
    q.put(None)

def consumer():
    window = []
    features_list = []
    
    while True:
        data = q.get()
        if data is None: break
        
        window.append(data['value'])
        if len(window) > 10: # Rolling window size = 10
            window.pop(0)
            
            # Extract features
            s = pd.Series(window)
            features = {
                'timestamp': data['timestamp'],
                'rolling_mean': s.mean(),
                'rolling_std': s.std(),
                'roc': s.iloc[-1] - s.iloc[-2] if len(s) > 1 else 0
            }
            features_list.append(features)
            print(f"Processed: {features}")

    # Output
    pd.DataFrame(features_list).to_parquet("features.parquet")
    print("Pipeline finished. Saved to features.parquet")

if __name__ == "__main__":
    # threading
    t1 = threading.Thread(target=producer)
    t2 = threading.Thread(target=consumer)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()