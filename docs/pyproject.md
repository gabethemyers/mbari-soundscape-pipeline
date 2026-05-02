# Project Configuration

This project uses `pyproject.toml` for project metadata and dependencies.

## Installation

Install all runtime dependencies:

```bash
pip install -e .
```

Install with dev dependencies (pytest, syrupy):

```bash
pip install -e ".[dev]"
```


## Requirements.txt

`requirements.txt` is still available and can be used as an alternative:

```bash
pip install -r requirements.txt
```

Both methods install the same dependencies.
