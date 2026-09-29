import importlib.util

import pytest

HAS_FASTEMBED = importlib.util.find_spec("fastembed") is not None


def pytest_collection_modifyitems(config, items):
    """Omite los tests marcados ``embeddings`` si el extra no está instalado."""
    if HAS_FASTEMBED:
        return
    skip = pytest.mark.skip(reason="requiere: pip install -e .[embeddings]")
    for item in items:
        if "embeddings" in item.keywords:
            item.add_marker(skip)
