-- Daily ride volume and revenue per fleet (trend grain for BI).
CREATE OR REPLACE TABLE mart_daily_volume AS
SELECT
    f.fleet,
    d.date,
    d.weekday_name,
    d.is_weekend,
    count(*)                       AS rides,
    round(sum(f.total_amount), 2)  AS revenue,
    round(avg(f.fare_amount), 2)   AS avg_fare,
    round(avg(f.trip_distance), 2) AS avg_distance
FROM fact_trip f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY ALL
ORDER BY f.fleet, d.date;
