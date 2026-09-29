# Contribuir

## Entorno

```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e .[dev]            # añade ,embeddings para los tests semánticos
```

## Flujo por issue (la vida del proyecto)

Cada issue es un episodio del bucle de aprendizaje del propio repo ([`learning/README.md`](learning/README.md)):

1. **RETRIEVE**: `python -m scripts.devlog recall "<título del issue>"` (`--embedder fastembed` para búsqueda semántica). Lee las lecciones antes de elegir herramientas.
2. **Rama** `issue-<n>-<tema>`; la tarjeta del Project pasa a *In Progress*.
3. **Implementar** con tests. Cada test debe poder fallar: añade un control cuando el efecto pueda quedar oculto.
4. **Registrar** `learning/episodes/NNN-issue-<n>.json` con los fallos **tal como ocurrieron** (en la acción que los causó).
5. **CONSOLIDATE**: `python -m scripts.devlog rebuild`.
6. **PR** con `Closes #<n>`; merge squash **verificado** (`mergedAt`) antes de mover la tarjeta a *Done*.

## Comprobaciones (las mismas que CI)

```bash
ruff check . && ruff format --check .
mypy
pytest --cov                                # unit + integration, cobertura ≥ 90 %
python -m scripts.export_schema --check     # specs/memory_schema.json sincronizado
python -m scripts.mutation_check            # cada propiedad detecta su defecto inyectado
```

## Tests

| Carpeta | Qué contiene | Ejecutar |
|---|---|---|
| `tests/unit/` | Grafo, modelos, activación (valores a mano), consolidación, embeddings, configuración y **propiedades** (`hypothesis`) | `pytest tests/unit` |
| `tests/integration/` | Agente completo, benchmark, CLI, bitácora `learning/`, valencia contextual entre dominios | `pytest tests/integration` |

Los tests marcados `embeddings` requieren el extra `[embeddings]` y se omiten sin él.
Al añadir una propiedad, añade también su mutación en `scripts/mutation_check.py`: una propiedad que ninguna mutación rompe no está probando nada.

## Convenciones

- Código e identificadores en inglés; docstrings, docs y mensajes en español.
- Commits: `tipo(ámbito): descripción (#issue)` (`feat`, `fix`, `docs`, `build`, `test`, `chore`).
- `specs/memory_schema.json` es generado: cambia `src/associative_agent_loop/memory/models.py` y ejecuta `python -m scripts.export_schema`.
