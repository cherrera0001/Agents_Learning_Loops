---
name: auditor-datos
description: Comprobar que cada dato de un texto público viene de la medición que el texto dice, sobre el universo que dice y a la fecha que dice.
---

# Auditor de datos

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*: el procedimiento que esta skill proyecta.
- [`skills/proteger-evidencia`](../proteger-evidencia/SKILL.md): el auditor lee `evidence/`, `results/`
  y los datos crudos; no los modifica.
- [`skills/validador-estadistico`](../validador-estadistico/SKILL.md): el validador firma cada número; el
  auditor comprueba antes de qué medición sale y si sigue vigente.
- Episodio: `learning/episodes/063-issue-148-staff-datos-y-figuras.json`. El manuscrito del 2026-10-04
  decía «no hemos ejecutado el modelo» cuando el proyecto ya tenía seis corridas y tres envíos, y nadie
  lo había contrastado con la bitácora del experimento.

## Cuándo

Antes del validador estadístico, cada vez que un texto público reporta datos de un experimento que
siguió corriendo después de escribirse, o que mezcla mediciones de varias corridas.

## Procedimiento

1. **Inventario de mediciones.** Lista cada corrida, envío o control que el experimento registra (bitácora,
   registro de pruebas, `results/`), con fecha, configuración y conjunto de tareas.
2. **Vigencia.** Para cada afirmación del texto: vigente, desactualizada (da el dato nuevo y su fuente),
   contradicha, o nunca ejecutada. Un «no hemos medido X» se comprueba contra el inventario.
3. **Universo.** Cada conteo lleva su conjunto: cuántas tareas, de qué repositorio, en qué corridas. Si
   dos cifras del texto usan conjuntos distintos (15 frente a 16, 30 frente a 43), el texto lo dice.
4. **Fuente de evidencia.** Separa tres cosas y exige que el texto las separe: controles sin modelo,
   corridas del modelo, y juicios de un revisor. Un juicio hecho con acceso a la solución es
   retrospectivo y se rotula así.
5. **Conjunto reservado.** Si un conjunto se presenta como no visto, comprueba en qué corrida dejó de
   serlo. Desde la segunda corrida sobre él es conjunto de desarrollo.
6. **Lo observado y lo interpretado.** Una nota de 0,06 es un dato; «4 de 58» es una lectura que depende
   de un denominador inferido. «El mismo archivo» exige que la identidad esté comprobada.
7. **Desviaciones.** Contrasta el diseño preregistrado con lo que se ejecutó. Lo que no se ejecutó se
   declara; lo que se ejecutó fuera del diseño se presenta como exploratorio.
8. **Procedencia.** Fecha de corte, huellas de configuración con su método de cálculo, versión de cada
   artefacto externo citado, y qué no puede publicarse (frontera de fuga, reglas de la competición).
9. **Hallazgos ausentes.** Lista lo medido que hoy es más sólido que lo que el texto reporta, con su
   denominador y cuántas veces se midió.
10. **Confidencialidad.** Ningún agregado de una sola unidad que identifique una tarea; ningún
    identificador, enunciado, parche o prueba.

## Vetos obligatorios

- Una afirmación de ausencia («no ejecutamos», «no medimos», «no sabemos por qué») que el inventario
  contradice.
- Una cifra sin universo, o dos universos distintos presentados como uno.
- Un juicio de revisor presentado como medición.
- Un diseño preregistrado presentado como ejecutado, o abandonado sin declararlo.

## Informe

- **Veredicto:** apto, apto con cambios o no publicar.
- **Inventario** de mediciones, con fecha y conjunto.
- **Tabla de vigencia:** afirmación, estado, dato vigente y fuente.
- **Hallazgos ausentes** y su solidez.
- **Lo que no pudiste comprobar.**

El auditor no edita archivos ni hace commit.
