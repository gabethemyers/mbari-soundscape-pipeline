# `daily_metadata.py`

Generates metadata for a single day, converts it to NDJSON, and uploads the result to S3.

## What It Does

- Runs `pbp meta-gen` for one target date.
- Converts the day's JSON output into NDJSON.
- Uploads the resulting file to `s3://mbari-soundscape-metadata/`.
- Writes a daily log to `logs/daily_metadata.log`.

## Run

```bash
python daily_metadata/daily_metadata.py --date 2025-04-05
```

If `--date` is omitted, the script uses yesterday's date.

## Arguments

- `--date` — target date in `YYYY-MM-DD` format

## Output

- `json/<year>/<yyyymmdd>.json`
- `ndjson/year=<year>/month=<month>/<yyyymmdd>.ndjson`
- `logs/daily_metadata.log`

## Failure Behavior

- Invalid dates exit immediately with an error.
- `pbp meta-gen` failures stop the script with a non-zero exit code.
- Conversion or upload failures are logged and reported.
