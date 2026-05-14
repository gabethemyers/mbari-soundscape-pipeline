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

## EC2

### Soundscape Metadata Cron Instance

- **Instance ID:** `i-04e435bf75cbe76bb`
- **Name:** Soundscape MetaData Generation
- **Type:** `t4g.medium` (Graviton2, 2 vCPU, 4 GiB RAM)
- **OS:** Amazon Linux
- **Region:** us-west-2
- **Authentication:** `aws configure` — credentials stored in `~/.aws/credentials` and `~/.aws/config`. Boto3 and other AWS SDKs pick them up automatically.

### Cost & Performance Optimization

The instance was downsized from a `c6g.2xlarge` ($198/mo) to a `t4g.medium` ($24/mo), achieving an **88% cost reduction** with no impact on performance.

The `pbp` metadata generation script runs for approximately 5 minutes each day, making the previous 8-core, 16 GiB setup significantly over-provisioned. The `t4g.medium` was selected to maintain 4 GiB of RAM as a safety buffer for memory-intensive JSON loading while leveraging burstable CPU credits for the daily task. The instance is configured with **unlimited** credit mode as a safety net, but the 5-minute daily run should consume well within the monthly credit balance.

### Directory Layout

- **Working directory:** `/home/ec2-user/mbari_open_soundscape_query/`
- **Venv:** `/home/ec2-user/mbari_open_soundscape_query/venv/`
- **PBP binary:** `/home/ec2-user/mbari_open_soundscape_query/venv/bin/pbp`
- **Logs:** `/home/ec2-user/mbari_open_soundscape_query/logs/`

### Cron Job

Runs daily at **8:00 AM PST** (16:00 UTC) via crontab:

```cron
0 16 * * * cd /home/ec2-user/mbari_open_soundscape_query && /home/ec2-user/mbari_open_soundscape_query/venv/bin/python -m mbari_soundscape_pipeline.daily_metadata >> /home/ec2-user/mbari_open_soundscape_query/logs/daily_metadata.log 2>&1
```

Omitting `--date` makes the script process yesterday's data.

### Manual Execution

```bash
cd /home/ec2-user/mbari_open_soundscape_query
venv/bin/python -m mbari_soundscape_pipeline.daily_metadata --date 2026-05-13
```

### Fix: Hardcoded `pbp` Path

The script calls `pbp` without a full path, which fails on EC2 due to a minimal cron PATH. Change the first element of the `cmd` list:

```python
cmd = [
    "/home/ec2-user/mbari_open_soundscape_query/venv/bin/pbp", "meta-gen",
    f"--recorder={RECORDER}",
    ...
]
```

### Checking Status

```bash
# View today's log
tail -f /home/ec2-user/mbari_open_soundscape_query/logs/daily_metadata.log

# Check recent cron runs
crontab -l

# Check instance health
aws ec2 describe-instance-status --instance-id i-04e435bf75cbe76bb
```

## Athena

- **Database:** `mbari_soundscape`
- **Table:** `soundscape_metadata`
- **Work group:** `primary`
- **Table location:** `s3://mbari-soundscape-metadata/`

See [`athena_queries.md`](athena_queries.md) for schema details and example queries.
