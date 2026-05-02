# `convert_to_ndjson`

Standalone utility for converting PBP JSON array files into newline-delimited JSON.

Imported from:

```python
from mbari_soundscape_pipeline.convert_to_ndjson import convert_file
```

## What It Does

- Recursively finds `.json` files under an input directory.
- Verifies each file contains a JSON array.
- Writes matching `.ndjson` files into the output directory, preserving the folder structure.

## Run

### CLI

```bash
convert-to-ndjson <input_dir> <output_dir>
```

### Module invocation

```bash
python -m mbari_soundscape_pipeline.convert_to_ndjson <input_dir> <output_dir>
```

Example:

```bash
convert-to-ndjson json/iclisten converted/iclisten
```

## Behavior

- Creates output directories as needed.
- Skips files that are not JSON arrays.
- Prints a line for each converted file.

## Exit Conditions

- The script exits with usage help if the argument count is wrong.
- It exits with an error if the input directory does not exist.
