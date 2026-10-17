# Pre-registro · Calibración offline de η_h, α y τ_seed sobre la bitácora

**Registro**: el commit que introduce este archivo (C0), hecho **antes** de implementar el harness y antes de
cualquier corrida. Cambiar este documento después de ver datos lo invalida en ese punto, y toda desviación se
reporta como tal en el informe de resultados.

**Carácter: exploratorio.** El autor conoce las tasas de fallo de la bitácora (`devlog base-rates`), el
informe de H7 (donde τ ya se varió sobre otro objeto) y los defaults de la biblioteca (§6.6 del README). **No**
corrió el harness, no calculó métricas por config y no leyó `benchmark/private/` para este análisis: sus
etiquetas causales indexan las tareas del Experimento 1 (EXP-01..09), no los episodios de desarrollo.

## 1. Pregunta

> Reproduciendo offline los episodios de `learning/episodes/`, ¿existe una combinación de la tasa hebbiana
> (η_h), el peso del canal semántico (α) y la similitud mínima de siembra (τ_seed) que reduzca la tasa de
> **fallo repetido** respecto de los defaults (η_h = 0.3, α = 0.7, τ_seed = 0.25)?

Es una calibración de parámetros del mecanismo sobre su propio registro de uso (dogfooding), no una campaña del
Experimento 1: no toca `evidence/`, no corre el solver acotado y no usa `benchmark/private/`.

## 2. Dos desviaciones respecto del planteamiento original

1. **Población: todos los episodios presentes (97 al 2026-10-15), no 43.** El "43" era la cifra del README con
   fecha 2026-10-02; la bitácora siguió creciendo. Se usan los 97 archivos ordenados por `seq`, sin congelar
   ningún prefijo. El punto de corte calibración/validación es paramétrico (`--calibrate-frac`, default 0.7 →
   67 calibración / 30 validación con 97 episodios).
2. **Etiqueta causal: `learning/failure_classes.json`, no `benchmark/private/`.** Las etiquetas privadas
   indexan tareas de Task Ledger y no aplican a fallos del proceso de desarrollo. La clasificación de causa es
   la del repo: primera clase, en el orden del archivo, cuyo patrón (regex sin distinguir mayúsculas) case con
   el `error` o `note` del paso. Se transcriben sus caveats al informe (clasificación por palabras; fracción
   «sin clase» reportada aparte, no absorbida).

Ajuste metodológico adicional: la mejor config se elige por su tasa en la **ventana de calibración**; la
comparación final contra defaults se reporta solo en la **ventana de validación**. Elegir y evaluar sobre la
misma ventana sería selección sesgada a favor de la ganadora.

## 3. Replay y métricas (definiciones exactas)

Replay **online** y fiel al ciclo del agente (§5 del README): para cada episodio i en orden de `seq` sobre
memoria vacía: `RETRIEVE(goal_i)` → medir → `record_goal` / `record_step` por paso →
`consolidate_episode(..., activation=activación del RETRIEVE)` → `add_lesson` por cada lección del episodio.
Nota: `devlog rebuild` consolida sin activación; este replay sí la pasa, como el ciclo real, y eso acopla
η_h con (α, τ_seed) exactamente como en el agente. Embedder léxico (el default de `recall`; determinista, sin
descargas).

Para cada paso fallido de un episodio, sea C la clase de su causa (§2.2) o `sin clase`:

- **denominador primario**: fallos con C ≠ `sin clase` **y causa conocida**: existe en el grafo, antes del
  episodio, un nodo lección cuya etiqueta clasifica a C (misma regla regex sobre la etiqueta).
- **acierto**: causa conocida y alguna lección **visible** — top 5 tras el filtro de misma-acción (#187), lo
  que muestra `recall -n 5` — clasifica a C.
- **fallo repetido**: causa conocida y no acierto.
- **RepeatedFailureRate (primaria)** = fallos repetidos / fallos con causa conocida.
- **Sensibilidad**: fallos repetidos / **todos** los fallos (incluidos los `sin clase`, que nunca cuentan como
  conocidos).

**Denominadores por ventana, explícitos en el informe** (addición del dueño): para calibración y validación
por separado — episodios, fallos totales, fallos `sin clase` con su tasa, fallos con causa conocida. Si el
denominador primario de validación quedara menor que 10, el informe lo declara límite y no infla la lectura.

## 4. Grid, selección y comparación

- Grid: η_h ∈ {0.1, 0.3, 0.5} × α ∈ {0.5, 0.7, 0.9} × τ_seed ∈ {0.1, 0.25, 0.4} (27 configs; el centro es la
  config default y se deduplica).
- Selección: menor RepeatedFailureRate primaria en **calibración**; desempates: menor tasa de sensibilidad,
  luego η_h más cercano al default, luego α, luego τ_seed.
- Comparación default-vs-ganadora en **validación**: tasas con intervalo de Wilson al 95 %, diferencia en
  puntos porcentuales con IC 95 % por bootstrap pareado sobre episodios (unidad de agrupación), y tabla de
  McNemar (discordantes b/c), todo descriptivo, sin claims de significancia (estilo del repo).
- **La tabla de comparación muestra, junto a la tasa de validación de la ganadora, su tasa en calibración**
  (addición del dueño), para dejar visible el posible sesgo del ganador.

## 5. Regla de decisión (pre-registrada por el dueño)

Se **recomienda** adoptar la config calibrada solo si reduce la tasa de fallo repetido en **≥ 5 puntos
porcentuales** sobre los episodios de validación (estimación puntual, primaria). Si no, se conservan los
defaults y se reporta el resultado negativo. La decisión de cambiar los defaults de la biblioteca es del
dueño: este trabajo, sea cual sea el desenlace, **no toca los defaults**.

## 6. Reproducción

```bash
python -m scripts.offline_calibration run --output results/offline-calibration-v1
python -m scripts.offline_calibration report --aggregates results/offline-calibration-v1/aggregates.json
```

`aggregates.json` se genera y no se edita a mano. Todo es determinista: misma versión de los episodios y del
código ⇒ mismos bytes.
