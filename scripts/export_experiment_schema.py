"""Export/check the separate Experiment 1 schema without altering old files."""

import argparse
import json
from pathlib import Path

from experiments.models import MemoryDocument, Reflection

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, model in (
        ("software_memory_schema_v1.json", MemoryDocument),
        ("reflection_schema_v1.json", Reflection),
    ):
        path = ROOT / "specs" / name
        text = (
            json.dumps(
                {"$schema": "https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()},
                indent=2,
            )
            + "\n"
        )
        if args.check:
            if path.read_text("utf-8") != text:
                raise SystemExit(f"Outdated schema: {name}")
        else:
            path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
