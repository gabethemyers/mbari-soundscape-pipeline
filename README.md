# MBARI Soundscape Metadata Pipeline

This repository generates and validates metadata for MBARI's MARS hydrophone audio. The pipeline uses [PBP](https://docs.mbari.org/pbp/) to produce JSON, converts that output to NDJSON, and uploads partitioned results to S3 for Athena querying.

## What Lives Here

- `run_meta_gen.py` — full monthly pipeline from raw audio to NDJSON and S3 upload.
- `compare_s3_bucket_counts.py` — yearly source-vs-metadata comparison against Athena.
- `convert_to_ndjson.py` — standalone JSON array to NDJSON converter.
- `daily_metadata/daily_metadata.py` — daily metadata generation and upload flow.

## Documentation

Each script has its own doc in `docs/`:

- `docs/README.md`
- `docs/run_meta_gen.md`
- `docs/compare_s3_bucket_counts.md`
- `docs/convert_to_ndjson.md`
- `docs/daily_metadata.md`

## Requirements

- Python 3.11
- AWS credentials configured for the scripts that talk to S3 or Athena
- `mbari-pbp` installed from `requirements.txt`

## Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Output Layout

- `json/iclisten/` — PBP JSON output
- `ndjson/` — Hive-partitioned NDJSON output
- `output/` — PBP logs
- `logs/` — pipeline logs
- `status.json` — progress tracker for the monthly pipeline

## Common Commands

```bash
python run_meta_gen.py
python compare_s3_bucket_counts.py
python convert_to_ndjson.py <input_dir> <output_dir>
python daily_metadata/daily_metadata.py --date 2025-04-05
```
