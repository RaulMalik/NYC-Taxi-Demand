-- Pickup demand and economics per zone, with centroids for mapping.
CREATE OR REPLACE TABLE mart_zone_demand AS
SELECT
    z.location_id,
    z.zone,
    z.borough,
    z.lat,
    z.lng,
    count(*)                          AS pickups,
    round(sum(f.total_amount), 2)     AS total_revenue,
    round(avg(f.fare_amount), 2)      AS avg_fare,
    round(avg(f.trip_distance), 2)    AS avg_distance,
    round(avg(f.trip_duration_min), 2) AS avg_duration_min
FROM fact_trip f
JOIN dim_zone z ON f.pickup_location_id = z.location_id
GROUP BY ALL
ORDER BY pickups DESC;
