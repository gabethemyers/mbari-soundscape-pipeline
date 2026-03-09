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
convert_to_ndjson.py   # NDJSON conversion utility (called internally)
status.json            # auto-generated; tracks completed and failed months
json/iclisten/         # PBP output, organized by year
output/                # PBP logs
ndjson/                # converted output in Hive-partitioned structure
```

---

## Running

### Full run

```bash
python run_meta_gen.py
```

Processes all months from July 2015 through March 2026 in parallel batches. As each month completes, its JSON output is immediately converted to NDJSON and written to the Hive-partitioned output directory.

### Testing with a single day

Before running the full dataset, validate the pipeline with a single day by temporarily replacing `MONTH_RANGES` at the bottom of the config section in `run_meta_gen.py`:

```python
MONTH_RANGES = [
    {
        "key": "2019-06",
        "year": 2019,
        "month": 6,
        "start": "20190601",
        "end": "20190601",
    }
]
```

Run the script and confirm that `json/iclisten/2019/20190601.json` and `ndjson/year=2019/month=6/20190601.ndjson` are created and that `status.json` shows `"2019-06"` as completed. Restore `MONTH_RANGES = generate_month_ranges()` before the full run.

### Recovery

If the script is stopped or crashes, rerun it. It reads `status.json` on startup, skips completed months, and retries any that failed. No manual intervention needed.

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
- **Parallel batches via multiprocessing** — PBP is bottlenecked by S3 network I/O, so running 10 processes in parallel is much faster than serial even on a small instance.
- **Immediate NDJSON conversion** — each month is converted as soon as it finishes so completed months are always in their final format and ready to upload, even if the script stops early.
- **Hive-partitioned output** — Athena requires `year=YYYY/month=M/` structure to prune partitions efficiently. Organizing locally this way means the S3 upload is a straight sync with no restructuring needed.