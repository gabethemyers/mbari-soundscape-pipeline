# `compare_s3_bucket_counts`

Compares yearly source audio counts against Athena metadata coverage.

## What It Counts

- Source audio files are counted from `pacific-sound-256khz-{year}`.
- Only `.wav` objects at least 50 MB are included.
- Athena counts use `COUNT(DISTINCT uri)` to avoid duplicate inflation.
- `Diff` is `Athena metadata records - source audio files`.

## Requirements

- AWS credentials with S3 list access and Athena query access
- Correct values for:
  - `ATHENA_DATABASE`
  - `ATHENA_TABLE`
  - `ATHENA_RESULTS_BUCKET`

## Run

### CLI

```bash
compare-s3-bucket-counts
```

### Module invocation

```bash
python -m mbari_soundscape_pipeline.compare_s3_bucket_counts
```

## Output

The script prints one row per year from 2015 through 2026, then prints totals and a note that fragmented `.wav` files under 50 MB are excluded from the source count.

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

## Failure Behavior

- Missing yearly buckets are treated as zero for the source side.
- Athena query failures raise an error for that year.
