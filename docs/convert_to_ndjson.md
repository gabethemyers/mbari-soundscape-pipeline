# `convert_to_ndjson.py`

Standalone utility for converting PBP JSON array files into newline-delimited JSON.

## What It Does

- Recursively finds `.json` files under an input directory.
- Verifies each file contains a JSON array.
- Writes matching `.ndjson` files into the output directory, preserving the folder structure.

## Run

```bash
python3 convert_to_ndjson.py <input_dir> <output_dir>
```

Example:

```bash
python3 convert_to_ndjson.py json/iclisten converted/iclisten
```

## Behavior

- Creates output directories as needed.
- Skips files that are not JSON arrays.
- Prints a line for each converted file.

## Exit Conditions

- The script exits with usage help if the argument count is wrong.
- It exits with an error if the input directory does not exist.
