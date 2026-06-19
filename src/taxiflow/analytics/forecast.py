"""Hourly ride-volume forecasting: a calendar/Fourier/lag GBM vs a seasonal-naive baseline."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from ..config import Settings
from ..duck import connect
from ..staging.clean import STAGED_PATH

log = logging.getLogger("taxiflow.forecast")

WEEK = 24 * 7
LAGS = (WEEK, 2 * WEEK)  # >= the 7-day horizon, so they never leak the test block


def build_series(fleet: str, start: str, end: str) -> pd.DataFrame:
    con = connect(read_only=True)
    df = con.execute(
        f"""SELECT date_trunc('hour', pickup_datetime) AS ds, count(*) AS y
            FROM read_parquet('{STAGED_PATH}')
            WHERE fleet = ? AND pickup_datetime >= ? AND pickup_datetime < ?
            GROUP BY 1 ORDER BY 1""",
        [fleet, start, end],
    ).df()
    con.close()
    if df.empty:
        return df
    full = pd.date_range(df["ds"].min(), df["ds"].max(), freq="h")
    df = df.set_index("ds").reindex(full, fill_value=0).rename_axis("ds").reset_index()
    df["y"] = df["y"].astype(float)
    return df


def _fourier(values: np.ndarray, period: int, k: int, name: str) -> dict:
    out = {}
    for i in range(1, k + 1):
        out[f"{name}_sin{i}"] = np.sin(2 * np.pi * i * values / period)
        out[f"{name}_cos{i}"] = np.cos(2 * np.pi * i * values / period)
    return out


def features(ds: pd.Series, origin: pd.Timestamp) -> pd.DataFrame:
    ds = pd.DatetimeIndex(ds)
    hour = ds.hour.to_numpy()
    dow = ds.dayofweek.to_numpy()
    how = dow * 24 + hour
    trend = (ds - origin).total_seconds().to_numpy() / 3600.0
    cols = {"hour": hour, "dow": dow, "is_weekend": (dow >= 5).astype(int), "trend": trend}
    cols.update(_fourier(hour, 24, 4, "d"))
    cols.update(_fourier(how, WEEK, 6, "w"))
    return pd.DataFrame(cols, index=range(len(ds)))


def _design(series: pd.DataFrame, lags=LAGS) -> pd.DataFrame:
    s = series.reset_index(drop=True)
    X = features(s["ds"], s["ds"].iloc[0])
    for lag in lags:
        X[f"lag_{lag}"] = s["y"].shift(lag).to_numpy()  # NaNs handled natively by HGB
    return X


def _fit_predict(series: pd.DataFrame, n_train: int):
    X = _design(series)
    y = series["y"].to_numpy()
    model = HistGradientBoostingRegressor(
        max_iter=500, learning_rate=0.06, max_depth=7, l2_regularization=1.0, random_state=7
    )
    model.fit(X.iloc[:n_train], y[:n_train])
    pred_test = np.clip(model.predict(X.iloc[n_train:]), 0, None)
    sigma = float(np.std(y[:n_train] - model.predict(X.iloc[:n_train])))
    return pred_test, sigma


def seasonal_naive(history: pd.Series, n_train: int, n_test: int, season: int = WEEK) -> np.ndarray:
    h = history.reset_index(drop=True)
    return np.array([h.iloc[n_train + i - season] for i in range(n_test)], dtype=float)


def score(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    err = y_pred - y_true
    nz = y_true > 0
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err**2))),
        "MAPE": float(np.mean(np.abs(err[nz] / y_true[nz])) * 100) if nz.any() else float("nan"),
        "sMAPE": float(np.mean(2 * np.abs(err) / (np.abs(y_true) + np.abs(y_pred) + 1e-9)) * 100),
    }


def backtest(series: pd.DataFrame, horizon: int = 24, folds: int = 3) -> pd.DataFrame:
    rows = []
    for fold in range(folds):
        cut = len(series) - (folds - fold) * horizon
        if cut <= 2 * WEEK:
            continue
        sub = series.iloc[: cut + horizon].reset_index(drop=True)
        pred, _ = _fit_predict(sub, cut)
        test = series.iloc[cut: cut + horizon]
        base = seasonal_naive(series["y"], cut, horizon)
        rows.append({"fold": fold, "model": "gbm", **score(test["y"], pred)})
        rows.append({"fold": fold, "model": "seasonal_naive", **score(test["y"], base)})
    return pd.DataFrame(rows)


def run_forecast(settings: Settings) -> dict:
    test_periods = settings.forecast.test_days * 24
    forecast_rows, metric_rows, cv_rows = [], [], []

    for fleet in settings.forecast.fleets:
        series = build_series(fleet, settings.window.start, settings.window.end)
        if len(series) < test_periods + 2 * WEEK:
            log.warning("series too short for %s; skipping forecast", fleet)
            continue

        cv = backtest(series, horizon=24, folds=3)
        if not cv.empty:
            cv["fleet"] = fleet
            cv_rows.append(cv)

        n_train = len(series) - test_periods
        pred, sigma = _fit_predict(series, n_train)
        test = series.iloc[n_train:]
        base = seasonal_naive(series["y"], n_train, test_periods)
        metric_rows.append({"fleet": fleet, "model": "gbm", **score(test["y"], pred)})
        metric_rows.append({"fleet": fleet, "model": "seasonal_naive", **score(test["y"], base)})

        forecast_rows.append(
            pd.DataFrame(
                {
                    "fleet": fleet,
                    "ds": test["ds"].to_numpy(),
                    "y_actual": test["y"].to_numpy(),
                    "yhat": pred,
                    "yhat_lower": np.clip(pred - 1.96 * sigma, 0, None),
                    "yhat_upper": pred + 1.96 * sigma,
                }
            )
        )

    if not forecast_rows:
        return {"forecasts": 0}

    forecasts = pd.concat(forecast_rows, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)
    cv = pd.concat(cv_rows, ignore_index=True) if cv_rows else pd.DataFrame()

    con = connect()
    con.register("fc_df", forecasts)
    con.execute("CREATE OR REPLACE TABLE mart_forecast AS SELECT * FROM fc_df")
    con.register("m_df", metrics)
    con.execute("CREATE OR REPLACE TABLE mart_forecast_metrics AS SELECT * FROM m_df")
    if not cv.empty:
        cv_summary = cv.groupby(["fleet", "model"], as_index=False)[
            ["MAE", "RMSE", "MAPE", "sMAPE"]
        ].mean()
        con.register("cv_df", cv_summary)
        con.execute("CREATE OR REPLACE TABLE mart_forecast_backtest AS SELECT * FROM cv_df")
    con.close()

    best = metrics.sort_values("RMSE").groupby("fleet").first()
    log.info("forecast done | best by RMSE:\n%s", best[["model", "RMSE", "MAPE"]].to_string())
    return {"forecasts": len(forecasts), "fleets": settings.forecast.fleets}
