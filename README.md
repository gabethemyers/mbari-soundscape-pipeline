# MBARI Soundscape Metadata Pipeline

Generates audio metadata for MBARI's MARS hydrophone dataset (July 2015 to March 2026) using the [PBP](https://docs.mbari.org/pbp/) tool, converts output to NDJSON, and organizes it into Hive-partitioned directories for upload to AWS S3 and querying via Athena.

---

## Overview

The source audio files live in the public S3 bucket `pacific-sound-256khz`. Each file is a 10-minute WAV recording named with a `MARS_YYYYMMDD_HHMMSS.wav` pattern. PBP reads these files and extracts metadata (URI, start time, end time, duration) into JSON files organized by year. This script runs that process across the full 11-year dataset, then converts the output to NDJSON in a structure Athena can query directly.

---

## Requirements

- Python 3.11 (required — `mbari-pbp` does not support 3.12+)

---

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Files

```
run_meta_gen.py        # main script
status.json            # auto-generated; tracks completed and failed months
json/iclisten/         # PBP output, organized by year
output/                # PBP logs
ndjson/                # converted output in Hive-partitioned structure
logs/                  # timestamped log file per run
```

---

## Running

### Full run

```bash
python run_meta_gen.py
```

Processes all months from July 2015 through March 2026 in parallel batches of 10. As each month completes, its JSON output is immediately converted to NDJSON and written to the Hive-partitioned output directory.

### Testing with a single day

Before running the full dataset, validate the pipeline with a single day by temporarily replacing `MONTH_RANGES` in the config section of `run_meta_gen.py`:

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

Run the script and confirm that `json/iclisten/2019/20190701.json` and `ndjson/year=2019/month=7/20190701.ndjson` are created and that `status.json` shows `"2019-07"` as completed. Restore `MONTH_RANGES = generate_month_ranges()` before the full run.

### Testing parallelism

To verify multiple workers run simultaneously without running full months, replace `MONTH_RANGES` with several single-day ranges across different years:

```python
MONTH_RANGES = [
    {"key": "2016-03", "year": 2016, "month": 3, "start": "20160301", "end": "20160301"},
    {"key": "2018-06", "year": 2018, "month": 6, "start": "20180601", "end": "20180601"},
    {"key": "2020-01", "year": 2020, "month": 1, "start": "20200101", "end": "20200101"},
    {"key": "2022-09", "year": 2022, "month": 9, "start": "20220901", "end": "20220901"},
    {"key": "2025-12", "year": 2025, "month": 12, "start": "20251201", "end": "20251201"},
]
```

Each entry takes a couple of minutes. Confirm that all five "Starting meta-gen" messages appear in the log.

### Recovery

If the script is stopped or crashes, rerun it. It reads `status.json` on startup, skips completed months, and retries any that failed. No manual intervention needed. Delete `status.json` to start fresh.

---

## Logging

Each run writes a timestamped log file to `logs/`, e.g. `logs/run_20260315_143022.log`. Log output is also mirrored to stdout. Every line includes a timestamp and the month key it belongs to, e.g.:

```
2026-03-15 16:32:09 [2018-06] Starting meta-gen
2026-03-15 16:33:00 [2018-06] Still running... (1m elapsed)
2026-03-15 16:33:01 [2018-06] Meta-gen completed
2026-03-15 16:33:01 [2018-06] NDJSON conversion succeeded
```

On failure, the log includes the full stderr traceback and the last 50 lines of pbp stdout to aid debugging.

---

## Output Structure

PBP writes one JSON file per day:

```
json/iclisten/
└── 2019/
    ├── 20190601.json
    └── 20190602.json
```

After conversion, NDJSON files are written in Hive-partitioned layout for Athena:

```
ndjson/
└── year=2019/
    └── month=6/
        ├── 20190601.ndjson
        └── 20190602.ndjson
```

Upload the contents of `ndjson/` to `s3://mbari-soundscape-metadata/` preserving this structure. Athena will discover partitions via `MSCK REPAIR TABLE`.

---

## Design Decisions

- **Monthly granularity** — each month takes ~30 minutes, so processing month by month limits the worst-case loss on a crash to one month instead of a full year.
- **Status file written after every month** — the script can be killed at any point and resume without re-running completed months. Failed months are retried automatically.
- **Parallel batches via multiprocessing** — PBP is bottlenecked by S3 network I/O, so running 10 processes in parallel is much faster than serial.
- **Queue-based logging** — worker processes cannot safely share a file handle. Workers put log messages onto a `multiprocessing.Queue` and a dedicated listener thread in the main process writes them to the log file, avoiding interleaved or corrupted output.
- **Heartbeat every 60 seconds** — each worker sends a "still running" message while waiting on the subprocess, so long-running months produce visible progress rather than silence.
- **Stdout to temp file** — pbp stdout is verbose and not useful on a clean run. It is written to a temporary file during processing, discarded on success, and only read (last 50 lines) if the subprocess fails.
- **Immediate NDJSON conversion** — each month is converted as soon as it finishes so completed months are always in their final format and ready to upload, even if the script stops early.
- **Hive-partitioned output** — Athena requires `year=YYYY/month=M/` structure to prune partitions efficiently. Organizing locally this way means the S3 upload is a straight sync with no restructuring needed.