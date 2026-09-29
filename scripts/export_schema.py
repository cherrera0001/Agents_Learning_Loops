"""Genera ``specs/memory_schema.json`` desde los modelos Pydantic.

Uso::

    python -m scripts.export_schema          # escribe el archivo
    python -m scripts.export_schema --check  # falla si el archivo está desactualizado
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from associative_agent_loop.memory.models import GraphDocument

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "specs" / "memory_schema.json"


def build_schema() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/cherrera0001/Agents_Learning_Loops/specs/memory_schema.json",
        "$comment": "GENERADO por scripts/export_schema.py desde src/memory/models.py. No editar a mano.",
        **GraphDocument.model_json_schema(),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = build_schema()
    if args.check:
        current = SCHEMA_PATH.read_text("utf-8") if SCHEMA_PATH.exists() else ""
        if current != content:
            sys.exit(f"{SCHEMA_PATH.name} desactualizado: ejecuta python -m scripts.export_schema")
        print(f"{SCHEMA_PATH.name} sincronizado")
    else:
        SCHEMA_PATH.write_text(content, "utf-8")
        print(f"escrito {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
