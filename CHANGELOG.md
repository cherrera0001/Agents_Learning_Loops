# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).
Cada cambio enlaza su issue; el aprendizaje asociado está en `learning/episodes/`.

## [Unreleased]

### Añadido
- Documentación: contrato de entorno (agentes, skills, harness) sin cambio de comportamiento: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/entorno.mdc`, `docs/entorno/` (glosario, agentes, harness, skills) y `skills/` con tres skills de entorno.
- Documentación del modelo de construcción (qué modelo de Claude construye cada issue, cómo se aplica y con qué fuerza), sin cambio de comportamiento: README § 3.2 y `docs/entorno/enrutamiento.md`.
- Documentación del caso real del sitio público `vinculaterritorio.cl`, sin cambio de comportamiento: `docs/entorno/caso-real-contacto-vt.md` al día (formulario, verificación post-despliegue, roles de la landing y qué está implementado, observado, inferido o hipotético), rol de cierre en `docs/entorno/agentes.md`, fila canónica en `docs/entorno/README.md` y enlace en README § 3.1. No es evidencia del Experimento 1.
- Documentación: registro visible del caso real del sitio público, sin cambio de comportamiento: resultados por clase (verde, rojo, peor que el control, no verificado, bloqueado en el dueño, obsoleto) contados desde los archivos, y un diagrama que solo une causa y desenlace cuando un archivo los enlaza.
- Documentación: staff de texto público con veto (investigador de papers, revisor redactor y validador estadístico), sin cambio de comportamiento: tres skills de entorno en `skills/`, sus definiciones en `.claude/agents/` y enlaces en `docs/entorno/agentes.md`, `docs/entorno/README.md` y README § 3.1.
- Documentación: el README dice qué presenta el experimento (pregunta, diseño, resultados a favor y en contra con su fuente, qué aporta y qué queda abierto), sin cambio de comportamiento ni de evidencia; corrige el número de tests y la cobertura y fecha las cifras de la bitácora. Las tres skills del staff entran en las tablas de `skills/README.md` y `docs/entorno/skills.md`; su fuente es el apartado nuevo «Revisión de un texto público» de `CONTRIBUTING.md`, y las fichas, los vetos concretos y el texto firmado quedan en el registro fechado `docs/entorno/revision-texto-publico-2026-10-02.md`.
- Documentación: el README resume las campañas posteriores a H4 (#58, H6 y H7) con su diagrama, actualiza la hoja de ruta con el issue abierto de H8, da numerador y denominador en la tabla histórica y corrige el número de mutaciones inyectadas (88, por grupo); `docs/entorno/agentes.md` añade el diagrama de la revisión de un texto público. Sin cambio de comportamiento ni de evidencia.
- Línea base de diagnóstico público opt-in (#58): pre-registro, agente `bounded-ast-repair-v1+diagnostic-v1` que lee la reproducción pública antes de decidir, receta `--campaign diagnostic-baseline-v1`, verificaciones aditivas del evaluador (rechaza mezclar políticas, repite cada decisión desde su recibo) y análisis pre-registrado. El agente por defecto y las campañas publicadas no cambian.
- Memoria de fallos con revisión opt-in (H6, #63), sin campaña: pre-registro, agente `bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1` que baja la prioridad de una estrategia que ya falló con la misma firma de D y una clave similar (τ = 0.5), condiciones A, A_N, C y C_N con dos pasadas de transferencia, receta `--campaign failure-memory-v1`, registros de fallo en recibos `memory_update` separados, verificaciones aditivas del evaluador (repite cada decisión, exige que cada registro cite un intento fallido anterior de su celda y que A y C no tengan registros), `scripts/analyze_failure_memory.py` y el suplemento `specs/failure_memory_protocol.md`. El agente por defecto, el de #58 y las campañas publicadas no cambian.
- Transferencia y contaminación de la memoria de fallos opt-in (H7, #65), sin campaña: pre-registro, agente `bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1+failure-transfer-v1` con alcance τ ∈ {0.5, 0.25, 0.1, 0} y placebo (la estrategia del registro se rota al construir `F`), 18 condiciones (bases A y C × sin memoria de fallos, real y placebo por τ) con una sola pasada de transferencia, receta `--campaign failure-transfer-v1`, verificaciones aditivas del evaluador (repite cada decisión con su τ y su placebo, ningún registro en A y C, ningún registro aplicado de la misma tarea, la cadena de registros de H6), `scripts/analyze_failure_transfer.py` con `helped` y `hurt` pareados contra la base, y el suplemento `specs/failure_transfer_protocol.md`. El agente por defecto, el de #58, el de H6 y las campañas publicadas no cambian.
- Campaña `failure-transfer-v1` (H7, #65): 2 830 recibos en `evidence/failure-transfer-v1/`, agregados y análisis en `results/failure-transfer-v1/` y lectura en `docs/results/failure-transfer.md`. Veredicto pre-registrado sobre la base asociativa: «contamina» (τ = 0.1). Con lecciones, la memoria de fallos entre tareas nunca ayudó. Sin lecciones ayuda dentro de una familia y daña entre familias, y ningún umbral de similitud léxica separa unas relaciones de otras.
- Campaña `failure-memory-v1` (H6, #63): 860 recibos en `evidence/failure-memory-v1/`, agregados y análisis en `results/failure-memory-v1/` y lectura en `docs/results/failure-memory.md`. Las tres reglas salen favorables («aprendió de su error sin contaminar»), pero la mejora es por repetición de la misma tarea, y la contaminación no se puso a prueba: 0 de 351 registros de otra tarea entraron en el alcance.
- Recuperación sembrada con una señal no léxica opt-in (H8, #98), sin campaña: agente `bounded-ast-repair-v1+trace-seed-v1` con el `plan()` por defecto, condiciones A, B, C_L (la siembra léxica de H4) y C_S (siembra con los archivos de la aplicación por los que pasa la traza de `test-0`, sin consulta léxica ni respaldo), con `test-0` antes de `RETRIEVE`, receta `--campaign nonlexical-seed-v1`, verificaciones aditivas del evaluador (repite cada recuperación y cada decisión desde su recibo, rechaza una semilla fuera de `Component`, una puntuación que no sale de la traza y material privado o causal en la siembra, exige la misma señal en las cuatro condiciones), `scripts/analyze_h8.py` con las reglas de validez y de decisión del pre-registro, y el suplemento `specs/nonlexical_seed_protocol.md`. El agente por defecto, `agent.py`, `memory.py`, los agentes de #58, H6 y H7 y las campañas publicadas no cambian.
- Campaña `diagnostic-baseline-v1` (#58): 396 recibos en `evidence/diagnostic-baseline-v1/`, agregados en `results/diagnostic-baseline-v1/` y lectura en `docs/results/diagnostic-baseline.md`: con el mismo diagnóstico, la memoria aporta en las tareas originales (+6/18 al primer intento en B y en C) y no hay diferencia en las engañosas (−2/18).
- Documentación: staff de experimento para cada vuelta de un experimento con modelo (#154), sin cambio de comportamiento: siete definiciones en `.claude/agents/` (arquitecto de IA, forense del arnés, analista de datos, QA de trayectorias, inteligencia pública, auditor del método y verificador limpio), la sección «Vuelta de un experimento con modelo» en `CONTRIBUTING.md` con el criterio de corrida válida y de decisión válida, y las skills de entorno `corrida-valida` y `concilio-de-experimento`.

### Corregido
- Rescate de Kaggle (#146): un archivo de salida cuyo nombre no cabe en una ruta de Windows ya no corta la descarga; se guarda acortado y `salidas.json` conserva su nombre. Un notebook o archivo que falle queda en `faltantes.json` y el guion sigue y sale con 4. El resumen dice de dónde sale el tamaño de la tabla. Al seguir una redirección, el token no va a un host que no es Kaggle. El registro de envíos incorpora el reenvío 56830336 (nota 0,05).
- Análisis y evaluador de la línea base de diagnóstico (#58), antes de la campaña: el análisis valida la campaña completa declarada, el evaluador exige `decision_inputs` exacto con `test-0` fallido y la coherencia agente↔política en los dos sentidos.

### Corregido
- Documentación (sin cambio de comportamiento ni de evidencia): el README separa la campaña histórica (6 tareas), la referencia v2 (9 tareas, 6 permutaciones) y el resultado negativo de H4; sustituye limitaciones y hoja de ruta obsoletas y distingue los hashes v1 (`checkout-bytes/v0`) de los v2 (`lf/v1`). `specs/loop_protocol.md` cita las rutas actuales de `core.py`, `models.py` y `test_learning.py` (#56).

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
