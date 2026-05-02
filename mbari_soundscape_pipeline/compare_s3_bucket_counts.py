#!/usr/bin/env python3

import time

import boto3
from botocore.exceptions import ClientError


START_YEAR = 2015
END_YEAR = 2026
SOURCE_BUCKET_TEMPLATE = "pacific-sound-256khz-{year}"
ATHENA_DATABASE = "mbari_soundscape"
ATHENA_TABLE = "soundscape_metadata"
ATHENA_RESULTS_BUCKET = "s3://mbari-soundscape-metadata-query-results/compare-s3-bucket-counts/"
AUDIO_EXTENSIONS = (".wav",)
MIN_VALID_AUDIO_SIZE_BYTES = 50 * 1024 * 1024
ATHENA_POLL_INTERVAL_SECONDS = 2


def count_source_objects(s3_client, bucket_name: str) -> int:
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        total = 0
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                size = obj.get("Size", 0)
                if key.lower().endswith(AUDIO_EXTENSIONS) and size >= MIN_VALID_AUDIO_SIZE_BYTES:
                    total += 1
        return total
    except ClientError:
        # Missing bucket or access issues should not stop the full comparison.
        return 0


def get_athena_metadata_record_count(athena_client, year: int) -> int:
    query = f"SELECT COUNT(DISTINCT uri) FROM {ATHENA_TABLE} WHERE year = {year}"
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_RESULTS_BUCKET},
    )
    query_execution_id = response["QueryExecutionId"]

    while True:
        execution = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = execution["QueryExecution"]["Status"]["State"]
        if status == "SUCCEEDED":
            break
        if status in {"FAILED", "CANCELLED"}:
            reason = execution["QueryExecution"]["Status"].get(
                "StateChangeReason",
                "No Athena failure reason provided.",
            )
            raise RuntimeError(
                f"Athena query failed for year {year}: {status}. {reason}"
            )
        time.sleep(ATHENA_POLL_INTERVAL_SECONDS)

    results = athena_client.get_query_results(
        QueryExecutionId=query_execution_id,
        MaxResults=2,
    )
    rows = results["ResultSet"]["Rows"]
    if len(rows) < 2:
        raise RuntimeError(
            f"Athena query for year {year} returned no count row."
        )

    return int(rows[1]["Data"][0]["VarCharValue"])


def main() -> None:
    s3 = boto3.client("s3")
    athena = boto3.client("athena")
    rows: list[tuple[int, int, int, int]] = []
    total_source_files = 0
    total_athena_metadata_records = 0

    for year in range(START_YEAR, END_YEAR + 1):
        source_bucket = SOURCE_BUCKET_TEMPLATE.format(year=year)

        source_files = count_source_objects(s3, source_bucket)
        athena_metadata_records = get_athena_metadata_record_count(athena, year)
        diff = athena_metadata_records - source_files

        rows.append((year, source_files, athena_metadata_records, diff))
        total_source_files += source_files
        total_athena_metadata_records += athena_metadata_records

    total_diff = total_athena_metadata_records - total_source_files

    year_width = max(len("Year"), max(len(str(row[0])) for row in rows))
    source_width = max(
        len("Source Audio Files (Valid)"),
        max(len(str(row[1])) for row in rows),
    )
    metadata_width = max(
        len("Athena Metadata Records"),
        max(len(str(row[2])) for row in rows),
    )
    diff_width = max(
        len("Diff"),
        max(len(f"{row[3]:+d}") for row in rows),
        len(f"{total_diff:+d}"),
    )

    header = (
        f"{'Year':<{year_width}}  "
        f"{'Source Audio Files (Valid)':>{source_width}}  "
        f"{'Athena Metadata Records':>{metadata_width}}  "
        f"{'Diff':>{diff_width}}"
    )
    separator = (
        f"{'-' * year_width}  "
        f"{'-' * source_width}  "
        f"{'-' * metadata_width}  "
        f"{'-' * diff_width}"
    )

    print(header)
    print(separator)
    for year, source_files, athena_metadata_records, diff in rows:
        print(
            f"{year:<{year_width}}  "
            f"{source_files:>{source_width}}  "
            f"{athena_metadata_records:>{metadata_width}}  "
            f"{diff:+{diff_width}d}"
        )

    print()
    print(
        "Source Audio Files (Valid) exclude fragmented .wav files smaller than 50 MB."
    )
    print(f"Total source audio files (valid, non-fragmented): {total_source_files}")
    print(f"Total Athena metadata records: {total_athena_metadata_records}")
    print(f"Total diff: {total_diff:+d}")


if __name__ == "__main__":
    main()
