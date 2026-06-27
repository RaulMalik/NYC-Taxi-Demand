import numpy as np

from taxiflow.analytics.forecast import (
    WEEK,
    _fit_predict,
    backtest,
    features,
    score,
    seasonal_naive,
)


def test_score_exact():
    s = score([10, 20, 30], [11, 19, 33])
    assert round(s["MAE"], 3) == round((1 + 1 + 3) / 3, 3)
    assert s["RMSE"] >= s["MAE"]


def test_features_columns(hourly_series):
    X = features(hourly_series["ds"], hourly_series["ds"].iloc[0])
    assert len(X) == len(hourly_series)
    assert {"hour", "dow", "trend", "d_sin1", "w_cos1"} <= set(X.columns)


def test_seasonal_naive_repeats_week(hourly_series):
    y = hourly_series["y"]
    pred = seasonal_naive(y, n_train=len(y) - 24, n_test=24, season=WEEK)
    assert np.allclose(pred, y.iloc[len(y) - 24 - WEEK: len(y) - WEEK].to_numpy())


def test_gbm_runs_and_predicts(hourly_series):
    s = hourly_series
    pred, sigma = _fit_predict(s, n_train=len(s) - 24)
    assert len(pred) == 24
    assert np.isfinite(pred).all()
    assert sigma >= 0
    cv = backtest(s, horizon=24, folds=2)
    assert {"gbm", "seasonal_naive"} <= set(cv["model"])
