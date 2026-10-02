---
name: validador-estadistico
description: Dar un veto o un visto bueno a cada número de un texto público, con su fuente en el repositorio.
---

# Validador estadístico

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md) (*Metrics and
  falsification*): definición de `LearningGain` y `MemoryUtilityRate`.
- [`results/README.md`](../../results/README.md): «No statistical significance or autonomous
  software-engineering learning claim».
- [`docs/results/h4-associative-vs-history.md`](../../docs/results/h4-associative-vs-history.md)
  (*Alcance*): conteos exactos de un diseño exhaustivo, sin inferencia estadística.
- [`docs/entorno/caso-real-contacto-vt.md`](../../docs/entorno/caso-real-contacto-vt.md): `delivered` de
  Resend y LCP de laboratorio.
- [`skills/proteger-evidencia`](../proteger-evidencia/SKILL.md): el validador lee `evidence/` y
  `results/`; no los modifica.
- Episodio: ninguno registra este procedimiento como lección.

## Cuándo

Antes de publicar cualquier texto con un número, una comparación o una palabra que suene a estadística.

## Procedimiento

1. **Lista cada número** del texto, uno por fila.
2. **Busca su fuente**: archivo y, si existe, recibo o comando que lo reproduce. Sin fuente, la fila dice
   «no está en el repo» y lleva veto.
3. **Decide fila por fila**: visto bueno o veto. No hay «aproximadamente bien».
4. **Reglas fijas**:
   - No hay inferencia estadística en el protocolo. Seis o nueve tareas, un proyecto, tres operadores y
     réplicas de la misma semilla no son una muestra. Las réplicas verifican determinismo.
   - `LearningGain` y `MemoryUtilityRate` son métricas de este laboratorio, no un ensayo.
   - `delivered` de Resend no es bandeja de entrada.
   - Un LCP de laboratorio no es CrUX.
   - La cobertura de tests no es una tasa de aprendizaje.
   - Un porcentaje se acompaña de su numerador y su denominador.
5. **Veto obligatorio**: si el texto afirma una ventaja de la memoria asociativa sobre el historial
   textual. H4 no la sostiene.
6. **También las palabras.** Cada «resuelve», «aprende» o «significativo» recibe su fila, con la fuente
   que lo sostiene o un veto.
7. **`LearningGain` es `metric(memoria) − metric(sin memoria)`**, conservando la dirección (protocolo,
   *Metrics and falsification*). No es `P(éxito | grafo) − P(éxito | sin memoria)`: escrito así se
   sustituye por la definición del protocolo o se quita.
8. **Qué se movió.** En EXP-04..06 el éxito final es 1 en las tres condiciones
   ([`results/README.md`](../../results/README.md)); cambiaron el primer intento y las iteraciones, y el
   historial textual empató con la asociativa. En H4 las dos condiciones con memoria empeoraron el primer
   intento frente a no tener memoria (0/18 frente a 6/18).
9. **Tokens y costo no están en los recibos.** Prometidos como métrica ya medida, veto.
10. Una cifra vigente que ya no coincide con su fuente es falsa, aunque fuera cierta en una versión
   anterior; una cifra fechada («tras el ciclo v0.2») se comprueba contra esa fecha.

## Vetos de contenido

Obligatorios si aparecen, para los tres roles:

| Frase | Por qué | Fuente |
|---|---|---|
| Una lección se promueve a skill, como si ya ocurriera | `promoted_to_skill` sigue sin implementarse | Protocolo: «Skill promotion and contradiction resolution remain future work»; [glosario](../../docs/entorno/glosario.md), término 4 |
| El siguiente paso es probar transferencia en software real | El Experimento 1 ya la probó, y H4 no se sostiene | README § 7.2; [`h4`](../../docs/results/h4-associative-vs-history.md) |
| «El MemoryGraph resuelve» la falta de coincidencia léxica en L3–L5 | En las tareas con señuelo la clave era léxica y el grafo citó el señuelo igual que el historial | `h4`, *Datos* e *Interpretación* 1 |
| «El aprendizaje altera positivamente las decisiones», como hecho general | En los señuelos las empeoró | `h4`, *Interpretación* 2 |
| DEPRECATED o SUPERSEDED como protocolo ya activo | La resolución de contradicciones es trabajo futuro; esos dos estados no aparecen en `specs/` ni en `src/` | Protocolo, misma frase |
| KV prefix caching, NRNE o un contexto partido en prefijo y sufijo, como arquitectura del repositorio | No están en este código. Como debate, se marcan «pregunta abierta» | Grep sin resultados en `src/` y `specs/` |
| LG como diferencia de probabilidades de éxito | Ver la regla 7 | Protocolo, *Metrics and falsification* |

## Informe

Veredicto (apto, apto con cambios o no publicar) y la tabla: número o palabra, frase, fuente, visto bueno
o veto.
