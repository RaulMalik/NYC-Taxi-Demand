import pandas as pd

from taxiflow.analytics.anomaly import _rule_reasons


def test_rules_flag_known_bad():
    df = pd.DataFrame(
        {
            "trip_distance": [2.0, 0.0, 1.0, 0.5],
            "fare_amount": [10.0, 12.0, 0.0, 80.0],
            "tip_amount": [2.0, 1.0, 0.0, 1.0],
            "avg_speed_mph": [15.0, 20.0, 10.0, 120.0],
        }
    )
    reasons = _rule_reasons(df)
    assert reasons.iloc[0] == ""
    assert "zero_distance" in reasons.iloc[1]
    assert "zero_fare" in reasons.iloc[2]
    assert "implausible_speed" in reasons.iloc[3]
    assert "fare_distance_mismatch" in reasons.iloc[3]
