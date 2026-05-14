# `daily_metadata`

Generates metadata for a single day, converts it to NDJSON, and uploads the result to S3.

## What It Does

- Runs `pbp meta-gen` for one target date.
- Converts the day's JSON output into NDJSON.
- Uploads the resulting file to `s3://mbari-soundscape-metadata/`.
- Writes a daily log to `logs/daily_metadata.log`.

## Run

### CLI

```bash
daily-metadata --date 2025-04-05
```

### Module invocation

```bash
python -m mbari_soundscape_pipeline.daily_metadata --date 2025-04-05
```

If `--date` is omitted, the script uses yesterday's date.

## Arguments

- `--date` — target date in `YYYY-MM-DD` format

## Output

- `json/<year>/<yyyymmdd>.json`
- `ndjson/year=<year>/month=<month>/<yyyymmdd>.ndjson`
- `logs/daily_metadata.log`

## Failure Behavior

### Within a run

- Invalid dates → exit immediately with an error.
- `pbp meta-gen` failures → exit with non-zero code (cron logs the failure).
- AWS credential failures → exit with non-zero code (cron logs the failure).
- NDJSON conversion failures → error is logged, script continues to end (no upload).
- S3 upload failures → error is logged, script exits normally.

### Missed days

There is no retry mechanism. If the cron job fails for a given day, that day is permanently missed unless manually re-run:

```bash
cd /home/ec2-user/mbari_open_soundscape_query
daily-metadata --date 2026-05-13
```

The next day's cron job will process "yesterday" (the day after the failed one), so failures create gaps but don't cascade.

## EC2 Deployment

This script runs on EC2 via a daily cron job. See [`aws.md`](aws.md) for instance details, cron schedule, and operational reference.

> **EC2 note:** The `pbp` binary must be referenced with its full path on the instance: `/home/ec2-user/mbari_open_soundscape_query/venv/bin/pbp`. The script calls `pbp` without a full path, which fails on EC2 due to a minimal cron PATH. See [`aws.md`](aws.md) for the fix.
