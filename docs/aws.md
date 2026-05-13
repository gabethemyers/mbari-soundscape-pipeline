# AWS Infrastructure

This document describes the AWS resources used by the MBARI Soundscape Metadata Pipeline.

## Region

All resources are in **us-west-2** (Oregon).

## Access

Access to the MBARI-owned S3 buckets requires **MBARI IAM credentials**. These are not publicly accessible.

## S3 Buckets

### Source Audio — MBARI Pacific Sound

- **Bucket:** `pacific-sound-256khz-{year}` (one bucket per year, e.g. `pacific-sound-256khz-2022`)
- **Access:** Public via [AWS Open Data Registry](https://registry.opendata.aws/pacific-sound/)
- **Contents:** Raw 256 kHz audio recordings from MBARI's MARS hydrophone, organized by year. Files are named with the recorder ID and date (e.g., `ICLISTEN20220101_*.wav`).

### Metadata — Pipeline Output

- **Bucket:** `mbari-soundscape-metadata`
- **Access:** MBARI IAM credentials required
- **Structure:** Hive-partitioned NDJSON output from the pipeline.

```
s3://mbari-soundscape-metadata/
├── year=2015/
│   ├── month=01/
│   │   ├── 20150101.ndjson
│   │   ├── 20150102.ndjson
│   │   └── ...
│   ├── month=02/
│   │   └── ...
│   └── ...
├── year=2016/
│   └── ...
├── ...
└── year=2026/
    └── ...
```

Each `YYYYMMDD.ndjson` file contains the soundscape metrics for that day, one JSON object per line.

### Athena Query Results

- **Bucket:** `mbari-soundscape-metadata-query-results`
- **Access:** MBARI IAM credentials required
- **Contents:** Athena query result files. Athena writes query results here by default.

## Athena

- **Database:** `mbari_soundscape`
- **Table:** `soundscape_metadata`
- **Work group:** `primary`
- **Table location:** `s3://mbari-soundscape-metadata/`

See [`athena_queries.md`](athena_queries.md) for schema details and example queries.
