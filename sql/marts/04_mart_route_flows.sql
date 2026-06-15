-- Top pickup -> dropoff flows with both centroids, for arc/flow maps.
CREATE OR REPLACE TABLE mart_route_flows AS
SELECT
    f.fleet,
    f.pickup_location_id,
    f.dropoff_location_id,
    pz.zone   AS pickup_zone,
    dz.zone   AS dropoff_zone,
    pz.borough AS pickup_borough,
    dz.borough AS dropoff_borough,
    pz.lat AS pickup_lat,  pz.lng AS pickup_lng,
    dz.lat AS dropoff_lat, dz.lng AS dropoff_lng,
    count(*)                       AS trips,
    round(avg(f.fare_amount), 2)   AS avg_fare,
    round(avg(f.trip_distance), 2) AS avg_distance
FROM fact_trip f
JOIN dim_zone pz ON f.pickup_location_id  = pz.location_id
JOIN dim_zone dz ON f.dropoff_location_id = dz.location_id
WHERE f.pickup_location_id <> f.dropoff_location_id
GROUP BY ALL
HAVING count(*) >= 5
ORDER BY trips DESC
LIMIT 500;
