def is_worth_it(
    num_services: int,
    incidents_per_month: int,
    avg_incident_duration_hours: float,
    downtime_cost_per_hour: float,
    expected_mttr_reduction_pct: float = 0.4,
    aiops_monthly_cost: float = 15_000,
):
    """
    Returns:
      {
        "monthly_value": float,
        "monthly_cost": float,
        "roi": float,
        "payback_months": float,
        "verdict": "worth_it" | "marginal" | "not_worth_it"
      }
    """

    monthly_loss = (
        incidents_per_month
        * avg_incident_duration_hours
        * downtime_cost_per_hour
    )

    monthly_value = (
        monthly_loss
        * expected_mttr_reduction_pct
    )

    monthly_cost = aiops_monthly_cost

    roi = monthly_value / monthly_cost

    if monthly_value == 0:
        payback_months = float("inf")
    else:
        payback_months = monthly_cost / monthly_value

    if roi > 1.5:
        verdict = "worth_it"
    elif roi > 1.0:
        verdict = "marginal"
    else:
        verdict = "not_worth_it"

    return {
        "monthly_value": monthly_value,
        "monthly_cost": monthly_cost,
        "roi": roi,
        "payback_months": payback_months,
        "verdict": verdict
    }


if __name__ == "__main__":

    print(
        is_worth_it(
            num_services=20,
            incidents_per_month=2,
            avg_incident_duration_hours=1,
            downtime_cost_per_hour=10000,
            aiops_monthly_cost=15000
        )
    )

    print(
        is_worth_it(
            num_services=100,
            incidents_per_month=5,
            avg_incident_duration_hours=2,
            downtime_cost_per_hour=20000,
            aiops_monthly_cost=25000
        )
    )

    # Ví dụ ngành thương mại điện tử
    # Mỗi giờ downtime có thể gây mất khoảng 50.000 USD
    print(
        is_worth_it(
            num_services=50,
            incidents_per_month=4,
            avg_incident_duration_hours=1.5,
            downtime_cost_per_hour=50000,
            aiops_monthly_cost=20000
        )
    )