# Verificación independiente del Experimento 1

**Objeto**: PR #40 (`experiment/software-learning-v02` @ `43971ff`), issues #24–#36 y #41.
**Método**: reimplementación de las comprobaciones a partir de `specs/software_learning_protocol.md`,
**sin importar el paquete `experiments`** ([`scripts/verify_experiment1.py`](../../scripts/verify_experiment1.py)),
réplica completa de la campaña, análisis de sensibilidad pre-registrado y verificación por mutación.
**Entorno**: Windows 11, Python 3.14.7, checkout limpio con `eol=lf`.

## Resumen

| Meta | Issue | Pregunta | Resultado |
|---|---|---|---|
| V1 | #31 | ¿El Experimento 0 sigue intacto? | ✅ `aal-benchmark --json` en `main@77818ac` es idéntico a la línea base `ca853fd` |
| V2 | #35 | ¿Los recibos son íntegros y trazables? | ✅ 144/144 hashes verificados; la alteración se detecta; el reporte cita exactamente los 144 recibos |
| V3 | #33 | ¿Hay fuga de información privada al solver? | ✅ 0 fugas; ninguna actualización de memoria proviene de transferencia; toda lección recuperada es de entrenamiento |
| V4 | #36 | ¿Las métricas publicadas son reconstruibles? | ✅ Las 27 métricas coinciden con una implementación independiente |
| V5 | #32 | ¿La campaña es reproducible? | ✅ 54/54 comportamientos idénticos en una réplica independiente · ⚠️ los hashes dependen del fin de línea (#42) |
| V6 | #34 | ¿Las salvaguardas del grafo tipado están verificadas? | ⚠️ 5/8 mutaciones detectadas; 3 salvaguardas implementadas pero sin tests (#43) |
| V7 | #24–#29 | ¿Cada defecto se reproduce y se repara? | ✅ 6/6 tareas: reproducción fallida antes de reparar y reparación en 18/18 corridas |
| V8 | #30 | ¿La evidencia previa reduce fallos en tareas relacionadas? | ✅ Soportada en este entorno acotado: 2.0 → 1.0 intentos, robusta a la elección de semillas (#44) |

## V4 · Métricas (partición de transferencia, 18 corridas por condición)

| Métrica | NO_MEMORY | TEXT_HISTORY | ASSOCIATIVE_MEMORY |
|---|---|---|---|
| TaskSuccessRate | 1.0 | 1.0 | 1.0 |
| FirstAttemptSuccessRate | 0.333 | 1.0 | 1.0 |
| IterationsPerTask | 2.0 | 1.0 | 1.0 |
| MemoryRetrievalPrecision | null | 0.333 | **1.0** |
| FalseRetrievalRate | null | 0.667 | **0.0** |
| MemoryUtilityRate | null | 0.667 | 0.667 |

Nota de interpretación: en una primera lectura, dos definiciones del protocolo se implementaron de forma
distinta a la del PR (*recuperadas* = lecciones **expuestas**, no citadas; *uso* = selección que **cita**
memoria aunque confirme la elección previa). El texto del protocolo respalda la interpretación del PR y el
verificador se alineó con ella.

## V5 · Réplica independiente

| Proyección | Réplica vs. publicado |
|---|---|
| Comportamiento (decisión, plan, parches, inspecciones, códigos de salida, resultado, lecciones recuperadas) | **54/54 idénticos** |
| Comportamiento + hashes de fuentes y tests | 0/54: el mismo archivo tiene bytes CRLF en el checkout original y LF en uno limpio |

La campaña es reproducible en comportamiento. El esquema de integridad no es portable entre configuraciones
de fin de línea (#42). El job de CI no lo detecta porque compara dos corridas dentro del mismo checkout.

## Análisis de sensibilidad del baseline (#44)

El prior sin memoria (`random.Random(seed).shuffle`) depende solo de la semilla. Las semillas 7, 11 y 23
cubren **2 de las 6** permutaciones posibles, y en ninguna `normalize_environment` va primero.

**Predicción registrada antes de ejecutar**: con las 6 permutaciones (semillas 1, 4, 5, 6, 7, 9), NO_MEMORY
da exactamente 2.0 intentos por tarea. **Resultado** (144 recibos, íntegros, sin fugas):

| Tarea | NO_MEMORY | TEXT_HISTORY | ASSOCIATIVE |
|---|---|---|---|
| EXP-04 (transferencia) | 2.0 | 1.0 | 1.0 |
| EXP-05 (transferencia) | 2.0 | 1.0 | 1.0 |
| EXP-06 (transferencia) | 2.0 | 1.0 | 1.0 |
| EXP-02 (entrenamiento) | 2.0 | **2.5** | 2.0 |
| EXP-03 (entrenamiento) | 2.0 | **2.5** | **2.5** |

- La ganancia en transferencia es **robusta** a la elección de semillas y uniforme entre familias.
- Aparece **transferencia negativa durante el entrenamiento**: una lección de otra causa desvía la primera
  estrategia. El historial textual la sufre en 2 tareas y la memoria asociativa en 1. Es una señal con 6
  corridas por celda, no una conclusión (#46).

## Decisiones que la memoria no cambió (#41)

En las 36 corridas de transferencia con memoria (campaña publicada y de sensibilidad por igual):

- 12 corridas no cambiaron la decisión, y en **las 12** el prior sin memoria ya era correcto.
- 24 corridas cambiaron la decisión, y **las 24** tuvieron éxito al primer intento.

La memoria corrigió el 100 % de los priors equivocados. `MemoryUtilityRate = 0.667` es el máximo posible
cuando el prior acierta un tercio de las veces; no indica recuerdos inútiles.

## V6 · Mutaciones sobre las salvaguardas (#34, #35)

Control sin mutación: suite en verde. Una primera ejecución con un entorno de subproceso restringido daba
«8/8 detectadas», pero el control **también fallaba**: ese resultado era inválido y se descartó.

| Mutación | Detectada por |
|---|---|
| Versión de esquema desconocida aceptada | `test_reflection_cannot_be_its_own_evidence` |
| Memoria de evaluación admitida | `test_reject_fabricated_evidence_and_transfer_admission` |
| Reflexión sin evidencia aceptada | `test_reflection_cannot_be_its_own_evidence` |
| Hash de recibo no verificado | `test_receipts_reject_overwrite_and_detect_tampering` |
| Publicación que sobrescribe | `test_receipts_reject_overwrite_and_detect_tampering` |
| Arista colgante aceptada | ❌ sobrevive (#43) |
| Ids de nodo duplicados aceptados | ❌ sobrevive (#43) |
| `MERGE`/`UPDATE` convertidos en `ADD` | ❌ sobrevive (#43) |

## V7 · Tareas (#24–#29)

| Tarea | Issue | Partición | Defecto reproducido | Reparada | Iteraciones (NO_MEM / TEXT / ASSOC) |
|---|---|---|---|---|---|
| EXP-01 | #24 | entrenamiento | 18/18 | 18/18 | 1–2 / 1–2 / 1–2 |
| EXP-02 | #25 | entrenamiento | 18/18 | 18/18 | 3 / 3 / 3 |
| EXP-03 | #26 | entrenamiento | 18/18 | 18/18 | 1–2 / 2–3 / 2–3 |
| EXP-04 | #27 | transferencia | 18/18 | 18/18 | 1–2 / 1 / 1 |
| EXP-05 | #28 | transferencia | 18/18 | 18/18 | 3 / 1 / 1 |
| EXP-06 | #29 | transferencia | 18/18 | 18/18 | 1–2 / 1 / 1 |

**Par engañoso (EXP-05)**: ambas memorias recuperaron EXP-02 (causa correcta) en 6/6 corridas y nunca EXP-01
(síntoma parecido). El control no llegó a engañar, probablemente por una pista léxica en el texto público (#45).

## Reproducir

```bash
# en un checkout del PR #40 (o de main tras su merge)
python -m scripts.verify_experiment1 --root .                                    # V2, V3, V4, V7, V8
python -m experiments run --seeds 7 11 23 --replicates 2 --evidence-dir evidence/replication
python -m scripts.verify_experiment1 --root . --evidence evidence/replication --reference evidence/runs   # V5
python -m experiments run --seeds 1 4 5 6 7 9 --replicates 1 --evidence-dir evidence/sensitivity
python -m scripts.verify_experiment1 --root . --evidence evidence/sensitivity --results none.json
```

## Alcance

Los resultados describen un [solver acotado](../entorno/glosario.md) con tres operadores escritos a mano, seis tareas de un único
proyecto y réplicas deterministas. No sustentan significancia estadística, aprendizaje autónomo de
ingeniería de software ni superioridad de la memoria asociativa sobre el historial textual (#41, #46).
