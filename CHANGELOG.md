# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).
Cada cambio enlaza su issue; el aprendizaje asociado está en `learning/episodes/`.

## [Unreleased]

### Añadido
- Documentación: contrato de entorno (agentes, skills, harness) sin cambio de comportamiento: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/entorno.mdc`, `docs/entorno/` (glosario, agentes, harness, skills) y `skills/` con tres skills de entorno.
- Documentación del modelo de construcción (qué modelo de Claude construye cada issue, cómo se aplica y con qué fuerza), sin cambio de comportamiento: README § 3.2 y `docs/entorno/enrutamiento.md`.
- Línea base de diagnóstico público opt-in (#58): pre-registro, agente `bounded-ast-repair-v1+diagnostic-v1` que lee la reproducción pública antes de decidir, receta `--campaign diagnostic-baseline-v1`, verificaciones aditivas del evaluador (rechaza mezclar políticas, repite cada decisión desde su recibo) y análisis pre-registrado. El agente por defecto y las campañas publicadas no cambian; la campaña aún no se ha ejecutado.

## [0.2.0] - 2026-09-29

### Añadido
- Bitácora de desarrollo como memoria asociativa: `learning/` y `scripts/devlog.py` (#11).
- Modelos Pydantic `Node`/`Edge`/`GraphDocument`, JSON Schema generado y migración v1 → v2 (#2).
- Embeddings (`LexicalEmbedder`, `FastEmbedEmbedder`) y siembra híbrida sobre todos los nodos con texto (#3).
- Activación propagada con umbral de disparo acumulado, refracción, fan-out y caminos explicativos (#4).
- Aprendizaje hebbiano acotado, `decay()` explícito y poda por `max_edges` (#5).
- Fase RETRIEVE, `Planner`, máquina de estados verificada y benchmark `--json` (#6).
- Valencia contextual basada en evidencia episódica y escenario `cross_domain` (#8).
- Paquete `associative_agent_loop`, CLI `aal-benchmark`, `AppConfig` (TOML + `AAL_*`), `GraphStore` con escritura atómica, logging (#9).
- Suite `tests/unit` + `tests/integration`, propiedades con `hypothesis`, verificación por mutación (`scripts/mutation_check.py`) y cobertura del 98 % (#7).

### Cambiado
- Dependencias: `pydantic` en el núcleo; extras `embeddings` y `dev`; Python ≥ 3.11 (#1).
- **Ruptura**: los imports pasan de `src.…` a `associative_agent_loop.…`; `python -m src.main` → `aal-benchmark` (#9).
- **Ruptura**: `Retriever(memory, similarity=…)` → `Retriever(memory, embedder=…, config=RetrievalConfig(…))` (#3, #4).

### Corregido
- La consolidación asociaba como resolución todo éxito posterior a un fallo (#13).
- Los CLI en Windows producían JSON no UTF-8 al redirigir stdout (#6).

## [0.1.0] - 2026-09-29

### Añadido
- Grafo de memoria (Goal/Action/Outcome/Concept), activación propagada, consolidación EMA, agente Plan-Act-Observe-Consolidate, escenarios weather/flaky y 16 tests.
