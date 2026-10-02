# Contribuir

## Entorno

```bash
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e .[dev]            # añade ,embeddings para los tests semánticos
```

## Flujo por issue (la vida del proyecto)

Cada issue es un episodio del bucle de aprendizaje del propio repo ([`learning/README.md`](learning/README.md)).
Quien lo ejecuta es un agente de entorno: empieza por [`AGENTS.md`](AGENTS.md), que remite al
[glosario](docs/entorno/glosario.md) y al [harness de entorno](docs/entorno/harness.md). Los pasos 1, 3, 5, 7
y el manejo de evidencia tienen skills de entorno: [`estimar-issue`](skills/estimar-issue/SKILL.md),
[`recall-antes-de-issue`](skills/recall-antes-de-issue/SKILL.md),
[`registrar-episodio`](skills/registrar-episodio/SKILL.md),
[`confirmar-cierre`](skills/confirmar-cierre/SKILL.md) y [`proteger-evidencia`](skills/proteger-evidencia/SKILL.md).

Este es el **único texto canónico** del ciclo; los demás documentos lo enlazan y, a lo sumo, muestran su
diagrama:

```text
Issue listo (plantilla) → ESTIMAR → In Progress → RETRIEVE → implementar (rama + PR) → episodio
→ CONSOLIDATE → CONFIRMAR → Done
```

0. **Issue listo**: escrito con la plantilla [`issue.md`](.github/ISSUE_TEMPLATE/issue.md) (o
   [`epica.md`](.github/ISSUE_TEMPLATE/epica.md)), con su *Tipo de cierre* y su *Evidencia requerida*.
1. **ESTIMAR** (orquestador), antes de que nadie empiece. La talla y el modelo de construcción salen de
   [`docs/estimation.md`](docs/estimation.md) y se aplican como indica
   [`docs/entorno/enrutamiento.md`](docs/entorno/enrutamiento.md). Se registra en dos sitios: la sección
   «Estimación v1» (con fecha) en el cuerpo del issue y los campos *Talla*, *Puntos*, *Incertidumbre*,
   *Riesgo* y *Modelo* del Project #5. *Modelo* es el modelo **previsto**; los puntos son tamaño
   relativo, no horas ni tokens. Procedimiento: skill [`estimar-issue`](skills/estimar-issue/SKILL.md).
2. **In Progress** (implementador): la tarjeta pasa a *In Progress* al crear la rama
   `issue-<n>-<tema>`.
3. **RETRIEVE**: `python -m scripts.devlog recall "<título del issue>"` (`--embedder fastembed` para
   búsqueda semántica). Lee las lecciones antes de elegir herramientas.
4. **Implementar** con tests y abrir el PR. Cada test debe poder fallar: añade un control cuando el efecto
   pueda quedar oculto. El PR lleva `Closes #<n>`, salvo que el *Tipo de cierre* sea «sistema externo»
   y falte la observación: entonces `Refs #<n>` ([criterios de cierre](docs/entorno/harness.md#criterios-de-cierre-por-tipo-de-trabajo)).
   El implementador no hace merge.
5. **Registrar** `learning/episodes/NNN-issue-<n>.json` con los fallos **tal como ocurrieron** (en la
   acción que los causó), más los bloques opcionales `estimate` y `outcome`
   ([formato](learning/README.md#formato-de-un-episodio)).
6. **CONSOLIDATE**: `python -m scripts.devlog rebuild`.
7. **CONFIRMAR** (orquestador), después del merge squash **verificado** (`mergedAt`) y no antes. Se
   comprueba el criterio de cierre según el tipo de trabajo y se escribe en el tablero y en el issue:
   *Verificación* = *Verificada* con la evidencia enlazada, *Modelo usado* y *Escaló*. Si falla,
   *Verificación* = *Fallida* y el issue se reabre si el merge lo cerró. Procedimiento: skill
   [`confirmar-cierre`](skills/confirmar-cierre/SKILL.md).
8. **Done**: una tarjeta en *Done* **no es un cierre confirmado**; el cierre confirmado es
   *Verificación* = *Verificada*. Las automatizaciones del Project #5 actúan en los dos sentidos: al
   mergear un PR con `Closes #<n>` mueven la tarjeta a *Done* antes de CONFIRMAR, y mover una tarjeta a
   *Done* a mano cierra el issue. Por eso nadie mueve a mano antes de CONFIRMAR, y CONFIRMAR termina con
   `python -m scripts.devlog board --since <n>` sin hallazgos: su regla 3 señala toda tarjeta en *Done*
   sin verificar.

Responsables: el **orquestador** estima y confirma; el **implementador** pasa a *In Progress*,
implementa y registra el episodio ([roles](docs/entorno/agentes.md)).

### Reglas del registro

- **La estimación se conserva.** Si cambia el alcance, se añade un comentario «Estimación v2» con fecha,
  motivo y evidencia; la v1 no se reescribe.
- **El modelo previsto no se sobrescribe.** El campo *Modelo* sigue siendo el previsto aunque se escale;
  el resultado va en *Modelo usado* y *Escaló*. *Modelo usado* es autoinformado salvo que exista una
  transcripción.
- **La verificación del cierre no va en el episodio.** El episodio se escribe antes del merge y
  quedaría obsoleto; la verificación vive en el tablero y en el issue.
- Campos, métricas y límites del piloto: [`docs/piloto-estimacion.md`](docs/piloto-estimacion.md).
  Chequeo de coherencia entre issues, tablero y episodios, de solo lectura:
  `python -m scripts.devlog board --since <n>` ([reglas](learning/README.md#chequeo-del-tablero)).

## Jerarquía: épica, issue, tareas

Tres niveles, definidos aquí y en ningún otro sitio:

| Nivel | Qué es | Reglas |
|---|---|---|
| **Épica** | Issue con la etiqueta `epic` y subissues ([`epica.md`](.github/ISSUE_TEMPLATE/epica.md)) | Solo si tres o más issues comparten un resultado. No se estima: muestra la suma de sus hijos. Se cierra con todos los hijos obligatorios cerrados y sus criterios propios cumplidos. |
| **Issue** | La unidad que se estima ([`issue.md`](.github/ISSUE_TEMPLATE/issue.md)) | Se asigna a un modelo o agente, tiene tarjeta en el Project #5 y se cierra. |
| **Tareas** | Lista de verificación en el cuerpo del issue | Sin tarjeta ni talla. |

Si un issue necesita subissues, se convierte en épica y deja de estimarse. No hay nivel «historia de
usuario».

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
