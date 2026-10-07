---
name: validador-estadistico
description: Dar un veto o un visto bueno a cada número de un texto público, con su fuente en el repositorio.
---

# Validador estadístico

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*: el procedimiento que esta skill proyecta. Lo demás son los textos que ese procedimiento aplica.
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
3. **Decide fila por fila**: visto bueno o veto.
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
11. **Firma.** Un texto solo está firmado si el validador lo leyó entero en esa versión exacta y su
    respuesta cita el conteo de caracteres sin vetar nada.

12. **Recuenta desde el crudo** cuando el crudo existe. Contrastar una cifra con la bitácora que la
    escribió no la verifica: la bitácora puede arrastrar un error propio.
13. **Dos medidas de variación no son una.** Las tareas que cambian de resultado entre dos corridas
    iguales y el cambio neto del total son cifras distintas (4 y 4 resueltas pueden esconder 2 tareas
    que cambiaron). Un aumento neto de dos no equivale a dos discordancias.
14. **Dos o tres repeticiones no fijan un umbral.** Una regla del tipo «solo cuenta si supera N» es
    operativa; como conclusión exige un test y un análisis de potencia, o lleva veto.
15. **No establecer una mejora no es establecer que no hay efecto.** «Ningún cambio mejoró» lleva veto si
    alguna fila de la tabla sube; lo defendible es «no se estableció una mejora reproducible».
16. **Evaluada no es cerrada.** En un balance de predicciones, «con veredicto» cuenta solo cumplidas y
    refutadas; las ilegibles, sin caso y no corridas van aparte.
17. **Universo de cada conteo.** Si el mismo fenómeno aparece con 15 y con 16, el texto dice de qué
    conjunto es cada uno.
18. **Un porcentaje se ata a su base** en la misma frase: «32 de 58 (55 %)», no «la mayoría de los 58
    (45 %)».
19. **Una mediana dice sobre quiénes.** Si incluye sesiones que nunca hacen lo medido, se dice cuántas.
20. **Firma con huella.** Además del conteo de caracteres, la firma cita el SHA-256 del archivo leído. Un
    cambio posterior, aunque sea de una frase, deja el texto sin firma.

## Vetos obligatorios

Son los cinco de `CONTRIBUTING.md`
([vetos obligatorios](../../CONTRIBUTING.md#revisión-de-un-texto-público)). Los vetos concretos de cada
revisión, con la frase y su fuente, van al registro fechado; el primero es
[registro del 2026-10-02](../../docs/entorno/revision-texto-publico-2026-10-02.md).

## Informe

Veredicto (apto, apto con cambios o no publicar) y la tabla: número o palabra, frase, fuente, visto bueno
o veto.
