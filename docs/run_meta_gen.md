# `run_meta_gen`

Monthly metadata pipeline for the full MARS hydrophone archive.

## What It Does

- Runs `pbp meta-gen` over the configured month ranges.
- Converts each month's JSON output into NDJSON.
- Uploads the NDJSON partition to `s3://mbari-soundscape-metadata/`.
- Records progress in `status.json` so interrupted runs can resume.
- Writes a timestamped log file under `logs/` and mirrors the log stream to stdout.

## Requirements

- Python 3.11
- `pbp` on `PATH`
- AWS credentials for the S3 upload step

## Run

### CLI

```bash
run-meta-gen
```

### Module invocation

```bash
python -m mbari_soundscape_pipeline.run_meta_gen
```

## Configuration

All settings are defined as module-level constants near the top of `run_meta_gen.py`.

### Date Range

| Setting | Value | Description |
|---|---|---|
| `START_YEAR` | `2015` | First year to process |
| `START_MONTH` | `7` | Starting month (July) — only applies to `START_YEAR`; subsequent years begin in January |
| `END_YEAR` | `2026` | Last year to process |
| `END_MONTH` | `3` | Ending month (March) — only applies to `END_YEAR`; earlier years run through December |

The configured range covers 2015-07 through 2026-03 (131 months).

### Directories

| Setting | Value | Description |
|---|---|---|
| `STATUS_FILE` | `"status.json"` | Progress tracking file (root of repo) |
| `JSON_BASE_DIR` | `"json/iclisten"` | PBP JSON output base directory |
| `OUTPUT_DIR` | `"output"` | PBP output directory (logs, etc.) |
| `NDJSON_DIR` | `"ndjson"` | Converted NDJSON output directory (Hive-partitioned) |
| `LOG_DIR` | `"logs"` | Run log directory (timestamped per run) |
| `GAPS_LOG_FILE` | `"gaps.log"` | Gap detection log — written when `pbp meta-gen` detects no data for a month |

### AWS / S3

| Setting | Value | Description |
|---|---|---|
| `URI` | `"s3://pacific-sound-256khz"` | Source audio bucket URI |
| `S3_BUCKET` | `"mbari-soundscape-metadata"` | Destination bucket for NDJSON uploads |

### PBP Parameters

These are the `pbp meta-gen` arguments passed via the script, referencing the config constants they map to:

| Argument | Config Constant | Value | Description |
|---|---|---|---|
| `--recorder` | `RECORDER` | `ICLISTEN` | Audio instrument type |
| `--json-base-dir` | `JSON_BASE_DIR` | `json/iclisten` | Base directory for JSON metadata output |
| `--output-dir` | `OUTPUT_DIR` | `output` | Directory for PBP logs |
| `--uri` | `URI` | `s3://pacific-sound-256khz` | Source audio location (S3) |
| `--start` | `month_config['start']` | (dynamic) | Start date in `YYYYMMDD` format — generated per month range |
| `--end` | `month_config['end']` | (dynamic) | End date in `YYYYMMDD` format — generated per month range |
| `--prefix` | `PREFIX` | `MARS_` | S3 key prefix for source audio files |

### Operational

| Setting | Value | Description |
|---|---|---|
| `BATCH_SIZE` | `8` | Number of months processed in parallel (multiprocessing pool size) |

### Day-of-Month Logic

For `START_YEAR` / `START_MONTH` (2015-07), the start day is set to **28** (not 1). This aligns with the first available data in the source archive. All other months start on day 1.

### Timeout

Each `pbp meta-gen` invocation is monitored for a **90-minute** timeout (5400 seconds). If a month exceeds this, the process is terminated and the month is marked as failed (with a gap log entry if "no data" was detected in stderr).

## Validation

To test without a full run, temporarily replace `MONTH_RANGES` with a single day or a few short ranges, then restore `MONTH_RANGES = generate_month_ranges()` before production use.

### Single-day check

```python
MONTH_RANGES = [
    {
        "key": "2019-07",
        "year": 2019,
        "month": 7,
        "start": "20190701",
        "end": "20190701",
    }
]
```

Run the script and confirm `json/iclisten/2019/20190701.json` and `ndjson/year=2019/month=7/20190701.ndjson` are created, and that `status.json` shows `"2019-07"` as completed.

### Parallelism check

```python
MONTH_RANGES = [
    {"key": "2016-03", "year": 2016, "month": 3, "start": "20160301", "end": "20160301"},
    {"key": "2018-06", "year": 2018, "month": 6, "start": "20180601", "end": "20180601"},
    {"key": "2020-01", "year": 2020, "month": 1, "start": "20200101", "end": "20200101"},
    {"key": "2022-09", "year": 2022, "month": 9, "start": "20220901", "end": "20220901"},
    {"key": "2025-12", "year": 2025, "month": 12, "start": "20251201", "end": "20251201"},
]
```

Each entry takes a couple of minutes. Confirm that all five `Starting meta-gen` messages appear in the log.

## Output

- `json/iclisten/<year>/<yyyymmdd>.json`
- `ndjson/year=<year>/month=<month>/<yyyymmdd>.ndjson`
- `logs/run_<timestamp>.log`
- `status.json`

## Recovery

- Completed months are skipped on the next run.
- Failed months are retried on the next run.
- Delete `status.json` to start fresh.

## Logging

- Each worker emits a heartbeat every 60 seconds while `pbp meta-gen` is still running.
- Failure logs include the tail of the captured stderr so long-running errors are easier to diagnose.
- The script keeps a per-run log file in `logs/` with the run timestamp in the filename.

## Upload

- Each month is uploaded only after NDJSON conversion succeeds.
- Upload success is required before a month is marked complete.
- AWS credentials are checked before processing starts.

## Notes

- `pbp` stderr is redirected to a temporary file and only surfaced on failures.
- The local NDJSON layout matches the Hive partition structure used by Athena.
