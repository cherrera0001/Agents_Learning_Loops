"""Contrato de dependencias (#1): núcleo liviano, embeddings opcionales."""

import sys
import tomllib
from pathlib import Path

import pytest

PYPROJECT = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text("utf-8"))


def test_core_dependencies_are_minimal():
    deps = PYPROJECT["project"]["dependencies"]
    assert any(d.startswith("networkx") for d in deps)
    assert any(d.startswith("pydantic") for d in deps)
    assert not any(d.startswith(("fastembed", "sentence-transformers", "torch")) for d in deps)


def test_core_imports_without_embeddings_extra():
    import src.agent.core  # noqa: F401
    import src.memory.associative  # noqa: F401

    assert "fastembed" not in sys.modules


def test_pydantic_v2_available():
    import pydantic

    assert int(pydantic.VERSION.split(".")[0]) >= 2


@pytest.mark.embeddings
def test_fastembed_extra_is_importable():
    from fastembed import TextEmbedding

    assert callable(TextEmbedding)
