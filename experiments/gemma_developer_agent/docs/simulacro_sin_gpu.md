# Simulacro sin GPU de un envío (#103, #106)

`scripts/kaggle_simulacro.py` corre el arnés real de punta a punta contra un **modelo falso con guion**.
No mide al modelo: no dice cuántas tareas resolvería Gemma. Responde dos preguntas que compilar el zip no
responde, antes de gastar un envío o cuota de GPU:

1. **¿El envío pierde tareas por una causa mecánica?** Un «modelo» que siempre aplica el parche de
   referencia y entrega debe resolver la tarea. Si no la resuelve, el fallo es del envío o del arnés.
2. **¿Qué parámetros recibe de verdad el modelo?** El simulacro captura la petición que el arnés arma
   desde `configs/sampling.yaml`.

Este documento dice cómo se usa y qué se midió con él el 2026-10-04. No contiene enunciados, parches,
pruebas, identificadores de tarea ni texto del arnés.

## Comando

```bash
python -m scripts.kaggle_simulacro \
  --envio <directorio del envío> \
  --tasks experiments/gemma_developer_agent/data/tasks.jsonl \
  --snapshots-dir experiments/gemma_developer_agent/data/snapshots \
  --resultados <directorio fuera de git o ignorado> \
  --task-ids <id> [<id> ...] \
  --imagen <imagen del sandbox> --python-arnes <python que tiene swegemma>
```

- `--python-arnes` es el intérprete del entorno del arnés (`docs/entorno_local.md`). El guion mismo solo usa
  la biblioteca estándar: sus tests corren sin el arnés y sin Docker.
- `--resultados` recibe la salida cruda del arnés, que trae salidas de pruebas: el guion se niega si la ruta
  queda versionable.
- El parche de referencia se lee de `tasks.jsonl` en esta máquina y solo viaja al sandbox local. Es un uso
  del evaluador (pre-registro, sección A): quien lo corre no redacta skills ni señuelos.
- Las tareas deben ser tareas que discriminan; con una que pasa sin parche el modo `mudo` no prueba nada.

Salida: 0 si todos los desenlaces son los esperados, 1 si alguno no lo es, 2 si la entrada es inválida.

## Los cuatro modos

| Modo | Qué hace el modelo falso | Desenlace esperado | Qué comprueba |
|---|---|---|---|
| `directo` | Aplica el parche con `run_command` y llama `submit_patch` | Resuelta | El camino normal: herramientas, extracción del parche y verificación |
| `subagente` | Antes llama al subagente que declara el envío | Resuelta | Que el subagente compila, responde y no rompe la sesión |
| `sin_submit` | Aplica el parche y termina sin entregar | Resuelta | Que el arnés rescata el diff del árbol de trabajo |
| `mudo` | No edita ni entrega | No resuelta | Que una sesión sin cambios no puntúa |

## Qué se midió el 2026-10-04

En un equipo local, con `swegemma` 0.2.7, sandbox Docker y dos tareas públicas que discriminan.

**El zip enviado (envío 56808559, SHA-256 `d8a3e1d3…`) no tiene fallos mecánicos en estos cuatro
caminos.** Las 8 corridas (2 tareas × 4 modos) dieron el desenlace esperado. La nota 0,06 no se explica
por un envío roto.

**Parámetros que recibe el modelo**, capturados de la petición:

| Envío | `max_completion_tokens` | `enable_thinking` | `thinking_token_budget` |
|---|---|---|---|
| Kit original (`include_thoughts: true`, 16 384) | 16 384 | `true` | 4 096 |
| Zip enviado (`include_thoughts: false`, 8 192) | 8 192 | **`false`** | no se envía |
| Zip enviado con `include_thoughts: true` | 8 192 | `true` | 4 096 |

`include_thoughts: false` **desactiva el razonamiento del modelo**; no se limita a ocultarlo. Con ese
valor el arnés envía `chat_template_kwargs.enable_thinking = false` y no envía presupuesto de
razonamiento, así que `thinking_budget: 4096` queda sin efecto. Lo mismo vale para el subagente. La
Enmienda 2 describía este cambio como una imitación de una configuración pública, sin decir qué hace; la
Enmienda 3 lo aclara.

No se sabe si desactivar el razonamiento ayuda o daña con un presupuesto de 4 minutos: sin razonar cada
turno es más corto y caben más turnos. Eso lo decide una corrida con el modelo, no este simulacro.

**El límite de 60 s por comando.** El arnés usa `timeout_seconds` para los comandos del agente, como
límite por defecto del sandbox y para la ejecución de las pruebas de verificación
(`swegemma/evaluate.py`, `swegemma/harness/verification.py`). Con el parche de referencia, las dos tareas
se resolvieron igual con 300, 60 y 20 segundos. En esas dos tareas el límite de 60 s no cambia el
veredicto. No dice nada de tareas con pruebas más lentas ni de los repositorios privados.

**Validez, como ensayo.** De tres tareas públicas con snapshot local, dos discriminan (fallan sin parche y
pasan con el de referencia) y una pasa sin parche. Es un ensayo local: el registro de validez que vale es
el de `scripts/kaggle_validez.py` en el entorno que fije el ensayo de notebook.

## Lo que el simulacro no cubre

- El modelo: carga, velocidad, calidad de las ediciones y uso del presupuesto.
- El guion de puntuación de Kaggle, que compacta y cachea el contexto; la CLI local no lo hace.
- El sandbox `subprocess` de los notebooks de Kaggle: aquí se usó Docker.
