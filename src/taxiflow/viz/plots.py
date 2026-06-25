"""Static + interactive figures rendered straight from the warehouse marts."""
from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402

from ..config import PATHS, Settings  # noqa: E402
from ..duck import connect  # noqa: E402

log = logging.getLogger("taxiflow.viz")
ACCENT = "#F2A900"
GREY = "#C9CDD2"


def _q(sql: str):
    con = connect(read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


def hourly_heatmap(fleet: str = "yellow"):
    df = _q(
        f"SELECT weekday, weekday_name, hour, avg_rides_per_day "
        f"FROM mart_hourly_volume WHERE fleet = '{fleet}'"
    )
    grid = df.pivot_table(index="weekday", columns="hour", values="avg_rides_per_day", fill_value=0)
    order = df.sort_values("weekday")["weekday_name"].unique()
    fig, ax = plt.subplots(figsize=(12, 4.5))
    sns.heatmap(grid, cmap="mako_r", ax=ax, cbar_kws={"label": "avg rides/day"})
    ax.set_yticklabels(order, rotation=0)
    ax.set_title(f"{fleet.title()} taxi — demand by weekday and hour")
    ax.set_xlabel("Pickup hour")
    ax.set_ylabel("")
    fig.tight_layout()
    return fig


def daily_trend():
    df = _q("SELECT fleet, date, rides FROM mart_daily_volume ORDER BY date")
    fig, ax = plt.subplots(figsize=(12, 4.5))
    for fleet, sub in df.groupby("fleet"):
        ax.plot(sub["date"], sub["rides"], label=fleet, linewidth=2)
    ax.set_title("Daily ride volume by fleet")
    ax.set_ylabel("Rides")
    ax.legend(frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig


def top_zones(n: int = 12):
    df = _q(f"SELECT zone, pickups FROM mart_zone_demand ORDER BY pickups DESC LIMIT {n}").iloc[::-1]
    colors = [ACCENT if i == len(df) - 1 else GREY for i in range(len(df))]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(df["zone"], df["pickups"], color=colors)
    ax.set_title(f"Top {n} pickup zones")
    ax.set_xlabel("Pickups")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig


def forecast_plot(fleet: str = "yellow"):
    fc = _q(f"SELECT * FROM mart_forecast WHERE fleet = '{fleet}' ORDER BY ds")
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(fc["ds"], fc["y_actual"], color="#3A3A3A", linewidth=1.6, label="actual")
    ax.fill_between(fc["ds"], fc["yhat_lower"], fc["yhat_upper"], color=ACCENT, alpha=0.25)
    ax.plot(fc["ds"], fc["yhat"], color=ACCENT, linewidth=2, label="forecast")
    ax.set_title(f"{fleet.title()} taxi — held-out forecast vs actual")
    ax.set_ylabel("Pickups / hour")
    ax.legend(frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig


def demand_map():
    try:
        import plotly.express as px
    except ImportError:
        return None
    df = _q("SELECT zone, borough, lat, lng, pickups, avg_fare FROM mart_zone_demand")
    fig = px.scatter_mapbox(
        df, lat="lat", lon="lng", size="pickups", color="pickups",
        color_continuous_scale="Inferno", size_max=40, zoom=9.5, hover_name="zone",
        hover_data={"borough": True, "pickups": ":,", "avg_fare": ":.2f", "lat": False, "lng": False},
        title="NYC taxi pickup demand by zone",
    )
    fig.update_layout(mapbox_style="open-street-map", margin=dict(l=0, r=0, t=40, b=0))
    return fig


def render_all(settings: Settings) -> dict:
    PATHS.figures.mkdir(parents=True, exist_ok=True)
    saved = []
    fleet = settings.forecast.fleets[0] if settings.forecast.fleets else "yellow"
    figs = {
        "hourly_heatmap": hourly_heatmap(fleet),
        "daily_trend": daily_trend(),
        "top_zones": top_zones(),
        "forecast": forecast_plot(fleet),
    }
    for name, fig in figs.items():
        out = PATHS.figures / f"{name}.png"
        fig.savefig(out, dpi=130, bbox_inches="tight")
        plt.close(fig)
        saved.append(out.name)

    fmap = demand_map()
    if fmap is not None:
        fmap.write_html(PATHS.figures / "demand_map.html", include_plotlyjs="cdn")
        saved.append("demand_map.html")

    log.info("rendered %d figures -> %s", len(saved), PATHS.figures)
    return {"figures": saved}
