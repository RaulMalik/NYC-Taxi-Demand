-- Average rides per day by fleet, weekday and pickup hour (BI heatmap grain).
CREATE OR REPLACE TABLE mart_hourly_volume AS
WITH base AS (
    SELECT f.fleet, f.pickup_hour AS hour, d.weekday, d.weekday_name, d.date
    FROM fact_trip f
    JOIN dim_date d ON f.date_key = d.date_key
),
days AS (
    SELECT fleet, weekday, count(DISTINCT date) AS n_days
    FROM base GROUP BY ALL
),
counts AS (
    SELECT fleet, weekday, weekday_name, hour, count(*) AS rides
    FROM base GROUP BY ALL
)
SELECT
    c.fleet, c.weekday, c.weekday_name, c.hour, c.rides, dd.n_days,
    round(c.rides::DOUBLE / dd.n_days, 2) AS avg_rides_per_day
FROM counts c
JOIN days dd USING (fleet, weekday)
ORDER BY c.fleet, c.weekday, c.hour;
