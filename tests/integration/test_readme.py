"""La documentación no puede divergir del código (#38).

La salida de referencia del README debe aparecer literalmente en la salida
real de ``aal-benchmark``: si un cambio altera los resultados, este test obliga
a actualizar la documentación en el mismo PR.
"""

import re
from pathlib import Path

from associative_agent_loop.main import benchmark, print_report

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
README = (ROOT / "README.md").read_text("utf-8")


def reference_lines() -> list[str]:
    block = re.search(r"Salida de referencia:\s*```text\n(.*?)```", README, re.S)
    assert block, "el README debe contener el bloque 'Salida de referencia'"
    return [line.rstrip() for line in block.group(1).splitlines() if line.strip()]


def test_readme_reference_output_matches_the_benchmark(capsys):
    print_report(benchmark())
    actual = {line.rstrip() for line in capsys.readouterr().out.splitlines()}
    stale = [line for line in reference_lines() if line not in actual]
    assert not stale, "README desactualizado; líneas que ya no produce aal-benchmark:\n" + "\n".join(stale)


def test_readme_cites_current_parameter_defaults():
    from associative_agent_loop.config import AppConfig

    cfg = AppConfig()
    for key, value in [
        ("alpha", cfg.retrieval.alpha),
        ("damping", cfg.retrieval.damping),
        ("firing_threshold", cfg.retrieval.firing_threshold),
        ("context_temperature", cfg.retrieval.context_temperature),
        ("hebbian_rate", cfg.consolidation.hebbian_rate),
        ("learning_rate", cfg.consolidation.learning_rate),
        ("decay_rate", cfg.agent.decay_rate),
    ]:
        row = re.search(rf"\| `{key}` \|[^|]*\| ([^|]+) \|", README)
        assert row, f"falta la fila de `{key}` en la tabla de parámetros"
        assert float(row.group(1)) == value, f"`{key}`: README {row.group(1)} ≠ código {value}"
