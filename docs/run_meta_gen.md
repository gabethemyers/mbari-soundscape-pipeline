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

Key settings live near the top of the script:

- `START_YEAR`, `START_MONTH`, `END_YEAR`, `END_MONTH` — date bounds used to generate the month list
- `STATUS_FILE` — progress tracking file
- `JSON_BASE_DIR` — PBP JSON output directory
- `NDJSON_DIR` — converted output directory
- `LOG_DIR` — run logs
- `S3_BUCKET` — upload destination
- `BATCH_SIZE` — number of months processed in parallel

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
