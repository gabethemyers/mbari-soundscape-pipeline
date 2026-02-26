#!/usr/bin/env python3
"""
Convert PBP JSON array files to newline-delimited JSON (NDJSON).
Recursively processes all .json files in the input directory and writes
converted files to the output directory, preserving the folder structure.

Usage:
    python3 convert_to_ndjson.py <input_dir> <output_dir>

Example:
    python3 convert_to_ndjson.py json/iclisten converted/iclisten
"""

import json
import sys
from pathlib import Path


def convert_file(input_path: Path, output_path: Path) -> None:
    with open(input_path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Skipping {input_path}: not a JSON array")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for record in data:
            f.write(json.dumps(record) + "\n")

    print(f"Converted: {input_path} -> {output_path}")


def convert_directory(input_dir: Path, output_dir: Path) -> None:
    json_files = list(input_dir.rglob("*.json"))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    print(f"Found {len(json_files)} JSON file(s) to convert\n")

    for input_path in json_files:
        relative_path = input_path.relative_to(input_dir)
        output_path = output_dir / relative_path
        try:
            convert_file(input_path, output_path)
        except Exception as e:
            print(f"Error converting {input_path}: {e}")

    print(f"\nDone. Converted files written to {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 convert_to_ndjson.py <input_dir> <output_dir>")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not input_dir.exists():
        print(f"Error: input directory '{input_dir}' does not exist")
        sys.exit(1)

    convert_directory(input_dir, output_dir)