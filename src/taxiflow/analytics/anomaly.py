"""Flag suspicious trips with IsolationForest plus interpretable business rules."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ..config import Settings
from ..duck import connect

log = logging.getLogger("taxiflow.anomaly")

_FEATURES = ["trip_distance", "fare_amount", "tip_amount", "total_amount",
             "trip_duration_min", "avg_speed_mph"]


def _rule_reasons(df: pd.DataFrame) -> pd.Series:
    reasons = [[] for _ in range(len(df))]
    rules = {
        "zero_distance": df["trip_distance"] <= 0,
        "zero_fare": df["fare_amount"] <= 0,
        "implausible_speed": df["avg_speed_mph"] > 80,
        "fare_distance_mismatch": (df["fare_amount"] > 60) & (df["trip_distance"] < 1),
        "tip_exceeds_fare": df["tip_amount"] > df["fare_amount"] * 1.5,
    }
    for name, mask in rules.items():
        for i in np.where(mask.to_numpy())[0]:
            reasons[i].append(name)
    return pd.Series([",".join(r) for r in reasons], index=df.index)


def run_anomaly(settings: Settings) -> dict:
    n = settings.anomaly.sample_rows
    con = connect()
    df = con.execute(
        f"SELECT trip_id, fleet, pickup_location_id, dropoff_location_id, {', '.join(_FEATURES)} "
        f"FROM fact_trip USING SAMPLE {n} ROWS"
    ).df()

    df = df.dropna(subset=_FEATURES).reset_index(drop=True)
    X = StandardScaler().fit_transform(df[_FEATURES])
    iso = IsolationForest(contamination=settings.anomaly.contamination, random_state=7, n_estimators=200)
    df["iso_outlier"] = iso.fit_predict(X) == -1
    df["anomaly_score"] = -iso.score_samples(X)

    df["rules"] = _rule_reasons(df)
    df["is_anomaly"] = df["iso_outlier"] | (df["rules"] != "")

    flagged = df[df["is_anomaly"]].sort_values("anomaly_score", ascending=False)
    summary = {
        "sampled": int(len(df)),
        "anomalies": int(df["is_anomaly"].sum()),
        "anomaly_rate": round(float(df["is_anomaly"].mean()), 4),
        "by_rule": {
            r: int(df["rules"].str.contains(r).sum())
            for r in ["zero_distance", "zero_fare", "implausible_speed",
                      "fare_distance_mismatch", "tip_exceeds_fare"]
        },
    }

    con.register("anom_df", flagged.head(10_000))
    con.execute("CREATE OR REPLACE TABLE mart_trip_anomalies AS SELECT * FROM anom_df")
    rule_summary = pd.DataFrame(
        [{"rule": k, "count": v} for k, v in summary["by_rule"].items()]
    )
    con.register("rule_df", rule_summary)
    con.execute("CREATE OR REPLACE TABLE mart_anomaly_summary AS SELECT * FROM rule_df")
    con.close()

    log.info("anomalies: %d/%d (%.2f%%)", summary["anomalies"], summary["sampled"],
             summary["anomaly_rate"] * 100)
    return summary
