from __future__ import annotations

from ..config import Settings

try:
    from pandera.pandas import Check, Column, DataFrameSchema
except ModuleNotFoundError:  # pandera < 0.20
    from pandera import Check, Column, DataFrameSchema


def trips_schema(settings: Settings) -> DataFrameSchema:
    c = settings.cleaning
    return DataFrameSchema(
        {
            "fleet": Column(str, Check.isin(settings.ingest.fleets)),
            "pickup_datetime": Column("datetime64[ns]", nullable=False, coerce=True),
            "dropoff_datetime": Column("datetime64[ns]", nullable=False, coerce=True),
            "pickup_location_id": Column(int, Check.in_range(1, 265), coerce=True),
            "dropoff_location_id": Column(int, Check.in_range(1, 265), coerce=True),
            "passenger_count": Column(float, Check.ge(0), nullable=True, coerce=True),
            "trip_distance": Column(float, Check.in_range(c.min_distance, c.max_distance), coerce=True),
            "fare_amount": Column(float, Check.in_range(c.min_fare, c.max_fare), coerce=True),
            "trip_duration_min": Column(
                float, Check.in_range(c.min_duration_min, c.max_duration_min), coerce=True
            ),
            "avg_speed_mph": Column(float, Check.ge(0), nullable=True, coerce=True),
            "pickup_hour": Column(int, Check.in_range(0, 23), coerce=True),
            "pickup_weekday": Column(int, Check.in_range(0, 6), coerce=True),
        },
        strict=False,
        coerce=True,
    )
