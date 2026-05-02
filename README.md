# MBARI Soundscape Metadata Pipeline

This pipeline processes passive acoustic monitoring data from MBARI's MARS hydrophone:
a cabled deep-sea observatory recording continuous broadband audio off the Monterey Bay 
coast. The source dataset, [MBARI Pacific Sound](https://registry.opendata.aws/pacific-sound/), 
has been recorded nearly continuously since July 2015 at 256 kHz resolution and is 
publicly available through the AWS Open Data Registry. This pipeline uses 
[PBP](https://docs.mbari.org/pbp/) to extract hourly soundscape metrics, converts the 
output to Hive-partitioned NDJSON, and uploads results to S3 for large-scale querying 
via AWS Athena. Both a monthly batch pipeline and a daily incremental flow are supported, 
with gap detection and upload validation built in.

## Quick Demo

### 1. Install dependencies

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -e .  # or: pip install -r requirements.txt
aws configure
```

`aws configure` sets up your AWS credentials so `boto3` can access S3 and Athena.

### 2. Run the monthly batch pipeline

```bash
python run_meta_gen.py
```

Processes all months in `MONTH_RANGES` (default: the full historical archive). Runs 8
months in parallel. Each month takes ~20 minutes on EC2 (~40 minutes on local hardware),
so a full backfill of ~10 years completes in a few hours with the parallelism. Progress
is tracked in `status.json` — interrupted runs resume where they left off.

### 3. Run a single-day incremental update

```bash
python daily_metadata/daily_metadata.py --date 2025-04-05
```

Processes one day's audio through PBP, converts to NDJSON, and uploads. Completes in
under a minute. If `--date` is omitted, the script processes yesterday's date.

### 3.5. Validate metadata coverage

```bash
python compare_s3_bucket_counts.py
```

Compares source audio file counts against Athena metadata records year by year. Expected
output looks like:

```
Year  Source Audio Files (Valid)  Athena Metadata Records  Diff
----  --------------------------  -----------------------  ----
2015                       20836                    20966  +130
2016                       48330                    48480  +150
2017                       51955                    51965   +10
2018                       50383                    50388    +5
2019                       50645                    50651    +6
2020                       50602                    50649   +47
2021                       50279                    50282    +3
2022                       50596                    50603    +7
2023                       49869                    49909   +40
2024                       36644                    36650    +6
2025                       36192                    36182   -10
2026                       16709                    16649   -60

Source Audio Files (Valid) exclude fragmented .wav files smaller than 50 MB.
Total source audio files (valid, non-fragmented): 513040
Total Athena metadata records: 513374
Total diff: +334
```

A near-zero diff indicates complete coverage. The small positive diff is expected and
attributable to fragmented audio files below the 50 MB validity threshold and a handful
of processing edge cases — the pipeline achieves **99.94% coverage**.

## Pipeline Overview

```mermaid
flowchart LR
    A[MARS Hydrophone - Raw Audio on S3] --> B[PBP - Metadata Extraction]
    B --> C[JSON Output]
    C --> D[NDJSON Conversion - Hive Partitioned]
    D --> E[S3 Upload]
    E --> F[AWS Athena - Queryable Metadata]
```

## Pipeline Modes

```mermaid
flowchart TD
    A[Monthly Batch - run_meta_gen.py] --> B[Backfill 10+ years of historical audio]
    B --> C[Iterates over date range with status.json tracking]

    D[Daily Incremental - daily_metadata.py] --> E[Runs once daily for new uploads]

    C --> F[PBP Extraction + NDJSON Conversion + S3 Upload]
    E --> F
```

## What Lives Here

- `run_meta_gen.py` — full monthly pipeline from raw audio to NDJSON and S3 upload.
- `compare_s3_bucket_counts.py` — yearly source-vs-metadata comparison against Athena.
- `convert_to_ndjson.py` — standalone JSON array to NDJSON converter.
- `daily_metadata/daily_metadata.py` — daily metadata generation and upload flow.
- `pyproject.toml` — project metadata and dependencies (see [docs/pyproject.md](docs/pyproject.md)).

## Documentation

Each script has its own doc in `docs/`:

- `docs/README.md`
- `docs/run_meta_gen.md`
- `docs/compare_s3_bucket_counts.md`
- `docs/convert_to_ndjson.md`
- `docs/daily_metadata.md`

## Requirements

- Python 3.11
- AWS credentials with S3 read/write and Athena query execution permissions
- `mbari-pbp` installed via `pip install -e .` or `pip install -r requirements.txt`

## Output Layout

- `json/iclisten/` — PBP JSON output
- `ndjson/` — hive-partitioned NDJSON output
- `output/` — monthly PBP logs (created by PBP)
- `logs/` — pipeline run logs including `daily_metadata.log`
- `status.json` — progress tracker for the monthly pipeline
- `daily_metadata/json/` — daily PBP JSON output
- `daily_metadata/logs/` — daily PBP logs (created by PBP)

## Contributions

Identified a silent-halt bug in `pbp meta-gen` triggered by missing source files
  in non-contiguous date ranges, affecting a significant portion of the historical
  archive. Reported as [issue #116](https://github.com/mbari-org/pbp/issues/116);
  the fix was implemented by mentor Danelle Cline, validated through pipeline testing
  on this project, and merged into PBP main via [PR #117](https://github.com/mbari-org/pbp/pull/117).

## Acknowledgments

Developed as part of a collaboration between CSUMB and MBARI under mentor Danelle Cline.
