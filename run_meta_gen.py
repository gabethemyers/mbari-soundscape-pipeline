# run_meta_gen.py
import json
import os
from pathlib import Path
import subprocess
import calendar
import datetime
import multiprocessing
import threading
import tempfile
import boto3

# --- Configuration ---

STATUS_FILE = "status.json"
JSON_BASE_DIR = "json/iclisten"
OUTPUT_DIR = "output"
NDJSON_DIR = "ndjson"
LOG_DIR = "logs"
GAPS_LOG_FILE = "gaps.log"
URI = "s3://pacific-sound-256khz"
PREFIX = "MARS_"
RECORDER = "ICLISTEN"
S3_BUCKET = "mbari-soundscape-metadata"
START_YEAR = 2015
START_MONTH = 7
END_YEAR = 2026
END_MONTH = 3


def generate_month_ranges() -> list[dict]:
    ranges = []
    for year in range(START_YEAR, END_YEAR + 1):
        start_month = START_MONTH if year == START_YEAR else 1
        end_month = END_MONTH if year == END_YEAR else 12
        for month in range(start_month, end_month + 1):
            last_day = calendar.monthrange(year, month)[1]
            start_day = 28 if year == START_YEAR and month == START_MONTH else 1
            ranges.append({
                "key": f"{year}-{month:02d}",
                "year": year,
                "month": month,
                "start": f"{year}{month:02d}{start_day:02d}",
                "end": f"{year}{month:02d}{last_day:02d}",
            })
    return ranges

MONTH_RANGES = generate_month_ranges()

# in months
BATCH_SIZE = 8

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
    for d in [JSON_BASE_DIR, OUTPUT_DIR, NDJSON_DIR, LOG_DIR]:
        os.makedirs(d, exist_ok=True)

# --- Logging ---

_LOG_QUEUE = None

def init_worker(log_queue):
    global _LOG_QUEUE
    _LOG_QUEUE = log_queue

def log_message(key: str, message: str):
    if _LOG_QUEUE is None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{ts} [{key}] {message}")
        return
    _LOG_QUEUE.put((key, message))

def log_listener(log_queue, log_path: Path):
    with open(log_path, "a", buffering=1) as f:
        while True:
            record = log_queue.get()
            if record is None:
                break
            key, message = record
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{ts} [{key}] {message}"
            print(line)
            f.write(line + "\n")

def append_gap_log(key: str):
    with open(GAPS_LOG_FILE, "a") as f:
        f.write(f"{key}: no data detected\n")

def log_gap_if_no_data(key: str, stderr_path: str, fallback_stderr: str | None = None) -> str:
    try:
        with open(stderr_path, "r") as stderr_reader:
            stderr_text = stderr_reader.read()
    except Exception:
        stderr_text = fallback_stderr or ""

    if "no data" in stderr_text.lower():
        append_gap_log(key)

    return stderr_text

def run_meta_gen(month_config: dict) -> tuple[str, str | None, str | None]:
    """Run pbp meta-gen for a single month. Returns (key, stdout, stderr)."""
    key = month_config["key"]
    log_message(key, "Starting meta-gen")
    try:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt") as stderr_file:
            stderr_path = stderr_file.name
            process = subprocess.Popen(
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
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                text=True,
            )

        wait_thread = threading.Thread(target=process.wait)
        start_time = datetime.datetime.now()
        wait_thread.start()
        while wait_thread.is_alive():
            wait_thread.join(timeout=60)
            if not wait_thread.is_alive():
                break
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            tail_lines = []
            try:
                with open(stderr_path, "r") as stdout_reader:
                    for line in reversed(stdout_reader.readlines()):
                        if line.strip():
                            tail_lines.append(line.strip())
                            if len(tail_lines) == 2:
                                break
                tail_lines.reverse()
            except Exception:
                tail_lines = []
            tail_text = f" Last stderr: {' | '.join(tail_lines)}" if tail_lines else ""
            log_message(
                key,
                f"Still running... ({int(elapsed // 60)}m elapsed){tail_text}",
            )
            if elapsed > 5400:
                process.terminate()
                log_gap_if_no_data(key, stderr_path)
                return (key, None, "Timed out after 90 minutes")

        _, stderr = process.communicate()
        log_gap_if_no_data(key, stderr_path, stderr)

        returncode = process.returncode
        if returncode != 0:
            last_lines = ""
            try:
                with open(stderr_path, "r") as stdout_reader:
                    lines = stdout_reader.readlines()
                last_lines = "".join(lines[-50:])
            except Exception:
                last_lines = ""
            if last_lines:
                stderr = (stderr or "") + "\n--- last 50 lines of stderr ---\n" + last_lines
            return (key, None, stderr if stderr else "")
        return (key, None, None)
    except Exception as e:
        return (key, None, str(e))
    finally:
        try:
            if "stderr_path" in locals() and stderr_path:
                os.unlink(stderr_path)
        except Exception:
            log_message(key, f"Warning: failed to delete temp file {stderr_path}")

def convert_month_to_ndjson(month_config: dict) -> tuple[bool, str | None]:
    """Convert a single month's PBP JSON files to NDJSON in Hive-partitioned structure."""
    year = month_config["year"]
    month = month_config["month"]
    key = month_config["key"]

    input_dir = Path(JSON_BASE_DIR) / str(year)
    output_dir = Path(NDJSON_DIR) / f"year={year}" / f"month={month:02d}"

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
            log_message(key, f"Converted: {input_path} -> {output_path}")
        except Exception as e:
            return (False, f"Error converting {input_path}: {e}")
    return (True, None)

def upload_month_to_s3(month_config: dict, s3_client) -> tuple[bool, str | None]:
    year = month_config["year"]
    month = month_config["month"]

    local_dir = Path(NDJSON_DIR) / f"year={year}" / f"month={month:02d}"
    if not local_dir.exists():
        return (False, f"NDJSON directory not found: {local_dir}")

    files = [path for path in local_dir.rglob("*") if path.is_file()]
    if not files:
        return (False, f"No NDJSON files found in {local_dir}")

    s3_prefix = f"year={year}/month={month}"
    for local_path in files:
        relative_path = local_path.relative_to(local_dir).as_posix()
        s3_key = f"{s3_prefix}/{relative_path}"
        try:
            s3_client.upload_file(str(local_path), S3_BUCKET, s3_key)
        except Exception as e:
            return (False, f"Error uploading {local_path}: {e}")
    return (True, None)
        
def main():
    ensure_dirs()
    run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(LOG_DIR) / f"run_{run_ts}.log"
    log_queue = multiprocessing.Queue()
    init_worker(log_queue)
    listener_thread = threading.Thread(target=log_listener, args=(log_queue, log_path))
    listener_thread.start()

    status = load_status()
    pending = get_pending_months(status)
    if pending:
        default_key = pending[0]["key"]
    elif status.get("failed"):
        default_key = next(iter(status["failed"]))
    elif status.get("completed"):
        default_key = status["completed"][0]
    else:
        default_key = "0000-00"

    log_message(default_key, f"Script start: {len(pending)} months pending.")

    if not pending:
        log_message(default_key, "All months already completed.")
        completed = len(status["completed"])
        failed = len(status["failed"])
        failed_keys = list(status["failed"].keys())
        summary = f"Script end: {completed} succeeded, {failed} failed."
        if failed_keys:
            summary = f"{summary} Failed months: {failed_keys}"
        log_message(default_key, summary)
        log_queue.put(None)
        listener_thread.join()
        return

    try:
        s3_client = boto3.client("s3")
        s3_client.list_buckets()
    except Exception as e:
        log_message(default_key, f"AWS credentials check failed: {e}")
        log_queue.put(None)
        listener_thread.join()
        return

    # split pending into batches of BATCH_SIZE
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]

    with multiprocessing.Pool(processes=BATCH_SIZE, initializer=init_worker, initargs=(log_queue,)) as pool:
        for index, batch in enumerate(batches, start=1):
            batch_by_key = {month["key"]: month for month in batch}
            batch_key = batch[0]["key"]
            batch_keys = ", ".join(batch_by_key.keys())
            log_message(batch_key, f"Batch {index}/{len(batches)} starting: {batch_keys}")
            results = pool.imap_unordered(run_meta_gen, batch)
            for key, stdout, stderr in results:
                if stderr is None:
                    log_message(key, "Meta-gen completed")
                    conversion_ok, conversion_error = convert_month_to_ndjson(batch_by_key[key])
                    if conversion_ok:
                        log_message(key, "NDJSON conversion succeeded")
                        log_message(key, "Uploading to S3...")
                        upload_ok, upload_error = upload_month_to_s3(batch_by_key[key], s3_client)
                        if upload_ok:
                            log_message(key, "S3 upload succeeded")
                            status["completed"].append(key)
                            status["failed"].pop(key, None)
                        else:
                            log_message(key, f"S3 upload failed: {upload_error}")
                            status["failed"][key] = upload_error
                    else:
                        log_message(key, f"NDJSON conversion failed: {conversion_error[:200]}")
                        status["failed"][key] = conversion_error
                else:
                    log_message(key, f"Meta-gen failed: {stderr[:200]}")
                    status["failed"][key] = stderr
                save_status(status)
            log_message(batch_key, f"Batch {index}/{len(batches)} completed: results collected")

    completed = len(status["completed"])
    failed = len(status["failed"])
    failed_keys = list(status["failed"].keys())
    summary = f"Script end: {completed} succeeded, {failed} failed."
    if failed_keys:
        summary = f"{summary} Failed months: {failed_keys}"
    log_message(default_key, summary)
    log_queue.put(None)
    listener_thread.join()

if __name__ == "__main__":
    main()
