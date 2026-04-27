# `compare_s3_bucket_counts.py`

Compares yearly source audio counts against Athena metadata coverage.

## What It Counts

- Source audio files are counted from `pacific-sound-256khz-{year}`.
- Only `.wav` objects at least 50 MB are included.
- Athena counts use `COUNT(DISTINCT uri)` to avoid duplicate inflation.
- `Diff` is `Athena metadata records - source audio files`.

## Requirements

- AWS credentials with S3 list access and Athena query access
- Correct values for:
  - `ATHENA_DATABASE`
  - `ATHENA_TABLE`
  - `ATHENA_RESULTS_BUCKET`

## Run

```bash
python compare_s3_bucket_counts.py
```

## Output

The script prints one row per year from 2015 through 2026, then prints totals and a note that fragmented `.wav` files under 50 MB are excluded from the source count.

TODO: add actual output example

## Failure Behavior

- Missing yearly buckets are treated as zero for the source side.
- Athena query failures raise an error for that year.
