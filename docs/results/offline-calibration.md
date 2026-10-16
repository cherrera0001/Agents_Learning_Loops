# Resultados · Calibración offline de η_h, α y τ_seed sobre la bitácora

**Lectura: resultado negativo, pre-registrado.** La mejor config del grid por la ventana de
calibración (η_h = 0.3, α = 0.7, **τ_seed = 0.4**) **no** reduce la tasa de fallo repetido en
validación: 57.3 % (67/117) frente a 56.4 % (66/117) de los defaults — Δ = **−0.9 pp**
(IC95 bootstrap [−10.7, +9.3]). Según la regla pre-registrada (umbral ≥ 5 pp), **no se recomienda
cambio y se conservan los defaults**. La decisión final es del dueño; este trabajo no tocó los
defaults. Pre-registro: [`docs/preregistration/offline-calibration.md`](../preregistration/offline-calibration.md).

## Trazabilidad

| Paso | Commit | Contenido |
|---|---|---|
| Pre-registro (C0) | `f0ee4e0` | Métricas, grid, reglas de selección y de decisión, **antes** de implementar y de correr |
| Implementación y tests | `4264567` | `scripts/offline_calibration.py`, `tests/integration/test_offline_calibration.py` (9 tests) |
| Corrección + re-corrrida | `f6c4af2` | McNemar contaba totales por config, no pares discordantes (9 tests en verde); `aggregates.json` regenerado |
| Datos y episodio | este commit | `results/offline-calibration-v1/aggregates.json` (generado) + episodio 100 |

`git diff f0ee4e0 -- docs/preregistration` está vacío tras la corrida: el pre-registro no cambió
al ver los datos. Desviaciones respecto del planteamiento original (97 episodios, no 43;
`failure_classes.json` en vez de `benchmark/private/`, cuyas etiquetas no aplican a episodios de
desarrollo; selección en calibración) venían fijadas en el propio C0.

```bash
python -m scripts.offline_calibration run --output results/offline-calibration-v1
python -m scripts.offline_calibration report --aggregates results/offline-calibration-v1/aggregates.json
```

## Datos

Replay online de los 97 episodios de `learning/episodes/` (seq 1..99 con huecos), embedder léxico
(el default de `devlog recall`), split temporal `--calibrate-frac 0.7`. **Denominadores por
ventana** (pedido explícito del dueño):

| Ventana | Episodios | Fallos | Sin clase | Con causa conocida |
|---|---|---|---|---|
| Calibración (seq 1–68) | 67 | 213 | 46 (21.6 %) | 160 |
| Validación (seq 69–99) | 30 | 144 | 27 (18.8 %) | 117 |

«Sin clase» = fallos que ningún patrón de `learning/failure_classes.json` clasifica; quedan fuera
del denominador primario (causa no etiquetada). Tasa de fallo repetido (repetidos / conocidos,
IC95 de Wilson): defaults 56.9 % (91/160) en calibración y 56.4 % (66/117) en validación. La
fracción «sin clase» está en el rango que el analista de datos estima para episodios nuevos
(20–30 %); las expresiones se escribieron leyendo los mismos episodios que clasifican (caveat del
propio archivo, transcrito en el agregado).

## Regla pre-registrada y resultado

Selección: menor tasa primaria en **calibración** (desempates: sensibilidad, |η_h−0.3|, |α−0.7|,
|τ_seed−0.25|). El grid 3×3×3 colapsa en **tres comportamientos distintos** (ver *Lo que la regla
no dice*): la tasa de calibración solo toma los valores 51.9 / 55.6 / 56.9 / 58.1 / 58.8 / 61.9 %
y la de validación 53.0 / 56.4 / 57.3 / 59.8 %.

**Comparación en validación** (default vs ganadora, con la tasa de calibración de la ganadora al
lado, pedido explícito del dueño):

| Config | Calibración | Validación | n (validación) |
|---|---|---|---|
| Default η_h=0.3 α=0.7 τ_seed=0.25 | 56.9 % (91/160) | 56.4 % | 66/117 |
| Ganadora η_h=0.3 α=0.7 τ_seed=0.4 | **51.9 %** (83/160) | **57.3 %** | 67/117 |

- Δ (default − ganadora) = **−0.9 pp**; IC95 bootstrap pareado [−10.7, +9.3] (10 000 remuestreos
  por episodio, semilla 7).
- McNemar (discordantes): 9 solo-default / 10 solo-ganadora; 57 repetidos bajo ambas, 41 bajo
  ninguna. Descriptivo, sin claim de significancia (estilo del repo).
- Regla de ≥ 5 pp: **no cumplida → resultado negativo → defaults se conservan**.

## Lo que la regla no dice

**1. Dos de los tres parámetros no mueven la métrica.** Con el embedder léxico, α es exactamente
inerte: ambos canales de la siembra híbrida computan el mismo coseno (verificado numéricamente;
`sim = α·cos + (1−α)·cos = cos`), así que las 27 filas del grid solo toman 9 valores distintos.
η_h tampoco mueve nada en esta replay: la creación de nodos lección es independiente de la tasa
hebbiana y la visibilidad (activación ≥ θ, corte top-5) queda saturada por las semillas a 1.0. En
la práctica el grid midió **un** parámetro, τ_seed, con tres niveles.

**2. La ventana elige al ganador y la ventana castiga.** τ_seed = 0.4 gana en calibración
(51.9 %) y pierde en validación (57.3 %); τ_seed = 0.1 hace lo contrario (58.8 % calibración,
53.0 % validación, la mejor tasa de validación del grid). Con diferencias de este tamaño entre
ventanas, la selección sobre 27 configs es mayormente ruido: la regla de ≥ 5 pp no se acercó a
cumplirse ni en valor absoluto (−0.9 pp).

**3. El denominador «causa conocida» es generoso.** Cuenta cualquier lección del grafo cuya
etiqueta clasifique a la misma clase regex que el fallo: una lección de «Entorno» hace «conocido»
cualquier fallo de Entorno, aunque lo que se repite sea otra cosa. La métrica es un proxy de
visibilidad de la recuperación, no de resultado (el repo ya registró este límite en el proxy
`RepeatedFailureRate` del Experimento 1).

**4. Lo que no se demuestra.** Que otro split, otro tamaño de grid o embeddings semánticos
(fastembed) cambien la conclusión; con n = 30 episodios de validación y tasas ~55 %, el IC de la
diferencia (±10 pp) no permite detectar efectos menores. La replay es determinista: dos corridas
del mismo commit dan los mismos bytes, pero no son observaciones independientes. El umbral de
decisión (5 pp) era del dueño y no se discute aquí; solo se aplica.

## Reproducción y determinismo

`run` escribe `aggregates.json` (generado, no editado a mano) en ~10 min; contiene las filas por
fallo de las 27 configs, los denominadores por ventana, la selección, la comparación y la
decisión. Mismos episodios y mismo código ⇒ mismos bytes. Suite completa en verde al cierre:
3487 passed, 5 skipped; ruff y `mypy` (src) limpios.
