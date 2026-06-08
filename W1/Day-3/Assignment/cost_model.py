from tabulate import tabulate

# Build
S3_STORAGE_COST_PER_GB = 0.023
LOG_INGEST_COST_PER_GB = 0.02
EC2_COST_PER_SERVICE = 15
NETWORK_COST_PER_GB = 0.01

DD_STORAGE_COST_PER_GB = 0.04      # retention cost (ước lượng)
DD_COMPUTE_COST_PER_MILLION = 0.05 # metrics processing
DD_NETWORK_COST_PER_GB = 0.02      # ingestion + transfer


def calculate_build_cost(services, log_gb_per_day, events_per_sec):
    days = 30
    monthly_log_gb = log_gb_per_day * days

    storage = monthly_log_gb * (S3_STORAGE_COST_PER_GB + LOG_INGEST_COST_PER_GB)
    compute = services * EC2_COST_PER_SERVICE
    network = monthly_log_gb * NETWORK_COST_PER_GB
    total = storage + compute + network

    return storage, compute, network, total


def calculate_buy_cost(log_gb_per_day, events_per_sec):
    days = 30
    monthly_log_gb = log_gb_per_day * days

    storage = monthly_log_gb * DD_STORAGE_COST_PER_GB
 
    monthly_events = events_per_sec * 3600 * 24 * days
    million_events = monthly_events / 1_000_000
    compute = million_events * DD_COMPUTE_COST_PER_MILLION
    
    network = monthly_log_gb * DD_NETWORK_COST_PER_GB
    total = storage + compute + network
    
    return storage, compute, network, total

tiers = {
    "Small": (10, 50, 100_000),
    "Medium": (100, 500, 1_000_000),
    "Large": (1000, 5000, 10_000_000)
}
def print_build():
    print("Build breakdown")
    table = []

    for tier, (s, log, ev) in tiers.items():
        st, cp, nw, tt = calculate_build_cost(s, log, ev)
        table.append([tier, f"${st:.2f}", f"${cp:.2f}", f"${nw:.2f}", f"${tt:.2f}"])

    print(tabulate(table, headers=["Tier", "Storage", "Compute", "Network", "Total"], tablefmt="grid"))


def print_buy():
    print("Buy breakdown")
    table = []

    for tier, (_, log, ev) in tiers.items():
        st, cp, nw, tt = calculate_buy_cost(log, ev)
        table.append([tier, f"${st:.2f}", f"${cp:.2f}", f"${nw:.2f}", f"${tt:.2f}"])

    print(tabulate(table, headers=["Tier", "Storage", "Compute", "Network", "Total"], tablefmt="grid"))


def print_compare():
    print("Build vs Buy ")
    table = []

    for tier, (s, log, ev) in tiers.items():
        _, _, _, build_total = calculate_build_cost(s, log, ev)
        _, _, _, dd_total = calculate_buy_cost(log, ev)

        table.append([
            tier,
            f"${build_total:.2f}",
            f"${dd_total:.2f}",
        ])

    print(tabulate(table, headers=["Tier", "Build", "buy"], tablefmt="grid"))


if __name__ == "__main__":
    print_build()
    print_buy()
    print_compare()