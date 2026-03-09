# run_meta_gen.py
import json
import os
from pathlib import Path
import subprocess
import calendar

# --- Configuration ---

STATUS_FILE = "status.json"
JSON_BASE_DIR = "json/iclisten"
OUTPUT_DIR = "output"
NDJSON_DIR = "ndjson"
URI = "s3://pacific-sound-256khz"
PREFIX = "MARS_"
RECORDER = "ICLISTEN"


def generate_month_ranges() -> list[dict]:
    ranges = []
    for year in range(2015, 2027):
        start_month = 7 if year == 2015 else 1
        end_month = 3 if year == 2026 else 12
        for month in range(start_month, end_month + 1):
            last_day = calendar.monthrange(year, month)[1]
            ranges.append({
                "key": f"{year}-{month:02d}",
                "year": year,
                "month": month,
                "start": f"{year}{month:02d}01",
                "end": f"{year}{month:02d}{last_day:02d}",
            })
    return ranges

MONTH_RANGES = generate_month_ranges()

# in months
BATCH_SIZE = 10

# --- Status File ---

def load_status() -> dict:
    """Load status from file, or return a fresh status dict if none exists."""
    if Path(STATUS_FILE).exists():
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "failed": {}}

def save_status(status: dict):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)


def get_pending_months(status: dict) -> list[dict]:
    completed = set(status.get("completed", []))
    return [m for m in MONTH_RANGES if m["key"] not in completed]


# --- Directory Setup ---

def ensure_dirs():
    for d in [JSON_BASE_DIR, OUTPUT_DIR, NDJSON_DIR]:
        os.makedirs(d, exist_ok=True)
        
def run_meta_gen(month_config: dict) -> tuple[str, str | None, str | None]:
    """Run pbp meta-gen for a single month. Returns (key, stdout, stderr)."""
    key = month_config["key"]
    try:
        result = subprocess.run(
            [
                "pbp", "meta-gen",
                f"--recorder={RECORDER}",
                f"--json-base-dir={JSON_BASE_DIR}",
                f"--output-dir={OUTPUT_DIR}",
                f"--uri={URI}",
                f"--start={month_config['start']}",
                f"--end={month_config['end']}",
                f"--prefix={PREFIX}",
            ],
            capture_output=True,
            text=True,
            timeout=2700
        )
        return (key, result.stdout, result.stderr if result.returncode != 0 else None)
    except subprocess.TimeoutExpired:
        return (key, None, "Timed out after 45 minutes")
    except Exception as e:
        return (key, None, str(e))

def convert_month_to_ndjson(month_config: dict) -> tuple[bool, str | None]:
    """Convert a single month's PBP JSON files to NDJSON in Hive-partitioned structure."""
    year = month_config["year"]
    month = month_config["month"]

    input_dir = Path(JSON_BASE_DIR) / str(year)
    output_dir = Path(NDJSON_DIR) / f"year={year}" / f"month={month}"

    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = list(input_dir.glob(f"{year}{month:02d}*.json"))

    if not json_files:
        return (False, f"No JSON files found for {month_config['key']}")

    for input_path in json_files:
        output_path = output_dir / input_path.with_suffix(".ndjson").name
        try:
            with open(input_path) as f:
                data = json.load(f)
            if not isinstance(data, list):
                return (False, f"Skipping {input_path}: not a JSON array")
            with open(output_path, "w") as f:
                for record in data:
                    f.write(json.dumps(record) + "\n")
            print(f"Converted: {input_path} -> {output_path}")
        except Exception as e:
            return (False, f"Error converting {input_path}: {e}")
    return (True, None)
        
def main():
    ensure_dirs()
    status = load_status()
    pending = get_pending_months(status)

    if not pending:
        print("All months already completed.")
        return

    print(f"{len(pending)} months remaining.")

    # split pending into batches of BATCH_SIZE
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]

    with multiprocessing.Pool(processes=BATCH_SIZE) as pool:
        for batch in batches:
            batch_by_key = {month["key"]: month for month in batch}
            results = pool.imap_unordered(run_meta_gen, batch)
            for key, stdout, stderr in results:
                if stderr is None:
                    conversion_ok, conversion_error = convert_month_to_ndjson(batch_by_key[key])
                    if conversion_ok:
                        print(f"{key}: success")
                        status["completed"].append(key)
                        status["failed"].pop(key, None)
                    else:
                        print(f"{key}: failed during NDJSON conversion - {conversion_error[:200]}")
                        status["failed"][key] = conversion_error
                else:
                    print(f"{key}: failed — {stderr[:200]}")
                    status["failed"][key] = stderr
                save_status(status)

    completed = len(status["completed"])
    failed = len(status["failed"])
    print(f"\nDone. {completed} succeeded, {failed} failed.")
    if status["failed"]:
        print("Failed months:", list(status["failed"].keys()))

if __name__ == "__main__":
    import multiprocessing
    main()
