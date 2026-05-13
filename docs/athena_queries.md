# Athena Queries

This document covers querying the `soundscape_metadata` table in AWS Athena.

## Table Schema

| Column | Type | Partitioned | Description |
|--------|------|-------------|-------------|
| `uri` | string | | S3 URI of the source audio file |
| `start` | string | | Start timestamp of the recording segment |
| `end` | string | | End timestamp of the recording segment |
| `duration_secs` | int | | Duration of the segment in seconds |
| `year` | int | Yes | Year partition |
| `month` | int | Yes | Month partition |

**Database:** `mbari_soundscape`

## Basic Queries

### Total records by year

```sql
SELECT year, COUNT(*) AS total_metadata_records
FROM soundscape_metadata
GROUP BY year
ORDER BY year;
```

### Total records by year and month

```sql
SELECT year, month, COUNT(*) AS total_records
FROM soundscape_metadata
GROUP BY year, month
ORDER BY year, month;
```

### Total records for a single year

```sql
SELECT month, COUNT(*) AS record_count
FROM soundscape_metadata
WHERE year = 2020
GROUP BY month
ORDER BY month;
```

### Total records for a single month

```sql
SELECT COUNT(*) AS total_files,
       MIN("start") AS first_file,
       MAX("end") AS last_file
FROM soundscape_metadata
WHERE year = 2025 AND month = 12;
```

### Count distinct URIs by year

```sql
SELECT year, COUNT(DISTINCT uri) AS file_count
FROM soundscape_metadata
GROUP BY year
ORDER BY year;
```

## Date Range Queries

### Query one day

```sql
-- Result: all files from 2018-05-15, only year=2018/month=05 partition scanned
SELECT uri, "start", "end"
FROM soundscape_metadata
WHERE year = 2018 AND month = 05
  AND "start" < '2018-05-16T00:00:00Z'
  AND "end" >= '2018-05-15T00:00:00Z';
```

### Query a single day with duration

```sql
-- Query one day and check coverage
SELECT uri, "start", "end", duration_secs
FROM soundscape_metadata
WHERE year = 2018 AND month = 01
  AND "end" >= '2018-01-01T00:00:00Z'
  AND "start" < '2018-01-02T00:00:00Z';
```

### Point-in-time lookup

```sql
-- Returns the file whose time window contains the given timestamp
SELECT uri, "start", "end", duration_secs
FROM soundscape_metadata
WHERE year = 2018 AND month = 06
  AND "start" <= '2018-06-10T14:35:00Z'
  AND "end" >= '2018-06-10T14:35:00Z';
```

### Cross-partition boundary query

```sql
-- Returns rows from both months when querying across a month boundary
SELECT month, COUNT(*)
FROM soundscape_metadata
WHERE (
  (year = 2018 AND month = 4) OR (year = 2018 AND month = 5)
)
AND "start" >= '2018-04-29T00:00:00Z'
AND "start" < '2018-05-03T00:00:00Z'
GROUP BY month;
```

### Records per day within a month

```sql
SELECT
    SUBSTR("start", 1, 10) AS record_day,
    COUNT(*) AS metadata_count
FROM soundscape_metadata
WHERE year = 2020 AND month = 8
GROUP BY SUBSTR("start", 1, 10)
ORDER BY record_day;
```

## Data Quality & Validation

### Check for duplicate URIs (same file, multiple records)

```sql
-- Check for duplicate files in a specific year
SELECT uri, COUNT(*) AS frequency
FROM soundscape_metadata
WHERE year = 2021
GROUP BY uri
HAVING COUNT(*) > 1
LIMIT 20;
```

### Partition anomaly detection

```sql
-- Compares the partition path (year/month) against the actual timestamp in the record.
-- Useful for detecting records that were written to the wrong partition.
SELECT
    year AS partition_year,
    month AS partition_month,
    SUBSTR("start", 1, 4) AS actual_year,
    SUBSTR("start", 6, 2) AS actual_month,
    COUNT(*) AS record_count
FROM soundscape_metadata
WHERE year != CAST(SUBSTR("start", 1, 4) AS INT)
   OR month != CAST(SUBSTR("start", 6, 2) AS INT)
GROUP BY 1, 2, 3, 4
ORDER BY record_count DESC;
```

### Duration consistency check

```sql
-- Finds records where duration_secs doesn't match the actual time span.
-- Expect: 0 rows (any mismatch indicates a data quality issue).
SELECT uri, duration_secs, "start", "end"
FROM soundscape_metadata
WHERE year = 2018 AND month = 1
  AND ABS(duration_secs - (
      to_unixtime(from_iso8601_timestamp("end"))
      - to_unixtime(from_iso8601_timestamp("start"))
  )) > 1;
```

### Files with very short or very long segments

```sql
SELECT uri, duration_secs
FROM soundscape_metadata
WHERE duration_secs < 60 OR duration_secs > 3700
LIMIT 100;
```

## DDL & Maintenance

### Create the table (for reference)

```sql
CREATE EXTERNAL TABLE soundscape_metadata (
  uri STRING,
  `start` STRING,
  `end` STRING,
  duration_secs INT
)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerde'
LOCATION 's3://mbari-soundscape-metadata/'
TBLPROPERTIES ('ignore.malformed.json' = 'true');
```

### Repair table partitions

```sql
MSCK REPAIR TABLE mbari_soundscape.soundscape_metadata;
```

## Notes

- **Reserved keywords:** `start` and `end` are reserved in SQL. Always surround them with double quotes (`"start"`, `"end"`).
- **Fragmented files:** Some `.wav` files on S3 are split into fragments under 50 MB. PBP `meta-gen` processes each fragment as a separate record, so one physical file may appear as multiple `uri` entries in Athena.
- **Duration filter:** To exclude very short recordings (likely fragments or edge cases), add `WHERE duration_secs >= 10`.
- **Partition pruning:** Always filter on `year` (and optionally `month`) to take advantage of partition pruning and reduce query cost.
