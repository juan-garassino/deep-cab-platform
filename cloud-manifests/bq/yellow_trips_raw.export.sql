-- Step 1 of the cross-region clone of nyc-tlc.yellow.trips into
-- garassino-ml:taxi.yellow_trips_raw (europe-west1).
--
-- BigQuery doesn't allow CREATE-TABLE-AS-SELECT across regions, so we:
--   1. EXPORT a slice from the US-located public table to a US GCS bucket
--      (this file).
--   2. `gsutil -m cp` the Parquet files to an EU GCS bucket.
--   3. `bq load --location=europe-west1` from the EU bucket into our target
--      table.
--
-- The CLI (`deepcab-platform data clone-bq`) renders the placeholders below
-- (${STAGING_BUCKET_US}, ${YEAR}) at invocation time and submits the rendered
-- SQL via `bq query --location=US`.
--
-- Cost: one-time ~€3 cross-region egress (~30 GB for 2014). To stay smaller,
-- pass --year + --max-rows; e.g. --max-rows 1_000_000 for a demo slice.
--
-- Filters: NYC-bounded lat/lon, fare/passenger sanity, time-window slice.

EXPORT DATA OPTIONS(
  uri='gs://${STAGING_BUCKET_US}/yellow_trips_raw_${YEAR}/*.parquet',
  format='PARQUET',
  overwrite=true,
  compression='SNAPPY'
) AS
SELECT
  vendor_id,
  pickup_datetime,
  dropoff_datetime,
  CAST(pickup_longitude  AS FLOAT64) AS pickup_longitude,
  CAST(pickup_latitude   AS FLOAT64) AS pickup_latitude,
  CAST(dropoff_longitude AS FLOAT64) AS dropoff_longitude,
  CAST(dropoff_latitude  AS FLOAT64) AS dropoff_latitude,
  CAST(passenger_count   AS INT64)   AS passenger_count,
  CAST(trip_distance     AS FLOAT64) AS trip_distance,
  CAST(fare_amount       AS FLOAT64) AS fare_amount,
  CAST(total_amount      AS FLOAT64) AS total_amount
FROM `nyc-tlc.yellow.trips`
WHERE pickup_datetime BETWEEN
        TIMESTAMP('${YEAR}-01-01 00:00:00')
    AND TIMESTAMP('${YEAR}-12-31 23:59:59')
  AND pickup_longitude  BETWEEN -75 AND -73
  AND pickup_latitude   BETWEEN  40 AND  42
  AND dropoff_longitude BETWEEN -75 AND -73
  AND dropoff_latitude  BETWEEN  40 AND  42
  AND fare_amount       BETWEEN   0 AND 400
  AND passenger_count   BETWEEN   1 AND   8
