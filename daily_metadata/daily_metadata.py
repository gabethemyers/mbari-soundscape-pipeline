import argparse
from datetime import date, datetime, timedelta
import subprocess
import sys
import boto3
import json
from pathlib import Path

JSON_BASE_DIR = "json"
NDJSON_DIR = "ndjson"
OUTPUT_DIR = "logs/meta-gen"
URI = "s3://pacific-sound-256khz"
PREFIX = "MARS_"
RECORDER = "ICLISTEN"
LOG_FILE = "logs/daily_metadata.log"
S3_BUCKET = "mbari-soundscape-metadata"

def convert_day_to_ndjson(target_date: date) -> tuple[bool, str | None]:
    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    day = target_date.strftime("%d")
    input_dir = Path(JSON_BASE_DIR) / year
    output_dir = Path(NDJSON_DIR) / f"year={year}" / f"month={month}"
    output_dir.mkdir(parents=True, exist_ok=True)

    matches = list(input_dir.glob(f"{year}{month}{day}.json"))
    if not matches:
        return (False, f"No JSON file found for {target_date}")

    input_path = matches[0]
    output_path = output_dir / input_path.with_suffix(".ndjson").name

    try:
        with open(input_path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            return (False, f"{input_path} is not a JSON array")
        with open(output_path, "w") as f:
            for record in data:
                f.write(json.dumps(record) + "\n")
        log_message(f"Converted: {input_path} -> {output_path}")
    except Exception as e:
        return (False, f"Error converting {input_path}: {e}")

    return (True, None)

def upload_day_to_s3(target_date: date, s3_client) -> tuple[bool, str | None]:
    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    day = target_date.strftime("%d")
    local_path = Path(NDJSON_DIR) / f"year={year}" / f"month={month}" / f"{year}{month}{day}.ndjson"
    if not local_path.exists():
        return (False, f"NDJSON file not found: {local_path}")
    s3_key = f"year={year}/month={month}/{year}{month}{day}.ndjson"
    try:
        s3_client.upload_file(str(local_path), S3_BUCKET, s3_key)
    except Exception as e:
        return (False, f"Error uploading {local_path}: {e}")
    return (True, None)

def log_message(message):
    with open(Path(LOG_FILE), "a", buffering=1) as f:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {message}"
        print(line)
        f.write(line + "\n")



def main():
    parser = argparse.ArgumentParser(description="Generate metadata for a specific date.")
    parser.add_argument(
        "--date", 
        type=str, 
        help="Target date as YYYY-MM-DD, defaults to yesterday"
    )
    args = parser.parse_args()

    if args.date:
        try: 
            target_date = date.fromisoformat(args.date)
        except ValueError as error:
            print(f"Error converting date: {error}")
            sys.exit(1)

    else:
        target_date = date.today() - timedelta(days=1)


    # pbp meta-gen call
    cmd = [
        "pbp", "meta-gen",
        f"--recorder={RECORDER}",
        f"--json-base-dir={JSON_BASE_DIR}",
        f"--output-dir={OUTPUT_DIR}",
        f"--uri={URI}",
        f"--start={target_date.strftime('%Y%m%d')}",
        f"--end={target_date.strftime('%Y%m%d')}",
        f"--prefix={PREFIX}",
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running pbp meta-gen: {e}")
        sys.exit(1)

    log_message("Meta-gen completed")

    # S3 credential check
    try:
        s3_client = boto3.client("s3")
        s3_client.list_buckets()
    except Exception as e:
        log_message(f"AWS credentials check failed: {e}")
        sys.exit(1)

    ## NDJSON conversion
    conversion_ok, conversion_error = convert_day_to_ndjson(target_date)

    if conversion_ok:
        log_message("NDJSON conversion succeeded")
        log_message("Uploading to S3...")
        upload_ok, upload_error = upload_day_to_s3(target_date, s3_client)
        if upload_ok:
            log_message("S3 upload succeeded")
        else:
            log_message(f"S3 upload failed: {upload_error}")
    else:
        log_message(f"NDJSON conversion failed: {conversion_error[:200]}")
        


if __name__ == "__main__":
    main()
