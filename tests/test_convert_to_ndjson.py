"""Tests for mbari_soundscape_pipeline.convert_to_ndjson"""
import json
from pathlib import Path

from mbari_soundscape_pipeline.convert_to_ndjson import convert_file


def test_convert_file(tmp_path):
    """A JSON array file gets converted to one line per record."""
    # Arrange: create a simple JSON array input
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps([{"id": 1}, {"id": 2}]))

    output_file = tmp_path / "output.ndjson"

    # Act
    convert_file(input_file, output_file)

    # Assert
    assert output_file.exists()
    lines = output_file.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"id": 1}
    assert json.loads(lines[1]) == {"id": 2}
