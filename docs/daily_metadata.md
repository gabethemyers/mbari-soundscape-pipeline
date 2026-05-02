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

- Invalid dates exit immediately with an error.
- `pbp meta-gen` failures stop the script with a non-zero exit code.
- Conversion or upload failures are logged and reported.

# Daily Metadata Cron Job setup

- **Instance:** EC2 Amazon Linux
- **Name:** Soundscape MetaData Generation
- **ID**: `i-04e435bf75cbe76bb`
- **Type**: c6g.2xlarge



## Fix: Hardcoded `pbp` Path in Script
 
Cron runs with a minimal PATH and couldn't find the `pbp` binary. Changed the `cmd` list in `daily_metadata.py` from:
```python
cmd = ["pbp", "meta-gen", ...]
```
 
To the full path:
```python
cmd = ["/home/ec2-user/mbari_open_soundscape_query/venv/bin/pbp", "meta-gen", ...]
```
 
 ## Cron Setup

Added the cron job via `crontab -e`:
```
0 16 * * * cd /home/ec2-user/mbari_open_soundscape_query/daily_metadata && /home/ec2-user/mbari_open_soundscape_query/venv/bin/python daily_metadata.py >> /home/ec2-user/mbari_open_soundscape_query/logs/daily_metadata.log 2>&1
```
Runs daily_metadata.py every day at 8am PST (4pm UTC).  

