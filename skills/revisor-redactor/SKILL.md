---
name: revisor-redactor
description: Reescribir un texto público del proyecto en español llano, sin anuncio y conservando el límite de lo medido.
---

# Revisor redactor

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Es personal de entorno para texto público: no es el agente de biblioteca ni el solver
> acotado, y no cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*: el procedimiento que esta skill proyecta. Lo demás son los textos que ese procedimiento aplica.
- [`README.md`](../../README.md) § 7.2, bloque «Qué no se demuestra», y § 12 (limitaciones).
- [`docs/results/h4-associative-vs-history.md`](../../docs/results/h4-associative-vs-history.md)
  (*Interpretación* y *Alcance*).
- [`docs/entorno/caso-real-contacto-vt.md`](../../docs/entorno/caso-real-contacto-vt.md) (*Qué se sabe y
  con qué fuerza*): implementado, observado, inferido e hipotético no se mezclan.
- [`docs/entorno/glosario.md`](../../docs/entorno/glosario.md): los siete términos.
- Episodio: ninguno registra este procedimiento como lección.

## Cuándo

Antes de publicar o de corregir un texto dirigido a alguien técnico que no vive en el repositorio: el
encabezado del README, un post o un artículo.

## Procedimiento

1. **Español, frases completas**, para alguien técnico que no vive en el repositorio.
2. **Quita el anuncio.** Fuera las preguntas retóricas, las cifras de gancho y los adjetivos de venta.
3. **Conserva el límite.** Todo texto dice qué se midió, en qué diseño (un proyecto, tres operadores
   escritos a mano, seis o nueve tareas) y **qué salió peor**. Un resultado negativo no se omite por
   espacio.
4. **Separa lo hecho de lo previsto.** Lo que el esquema declara pero el código no implementa (la skill
   de memoria, la resolución de contradicciones) se escribe en futuro o no se escribe.
5. **Palabras vetadas** si el validador estadístico no las firmó: «significativo», «aprende de verdad» y
   «memoria humana».
6. **Usa los nombres del glosario**: agente de biblioteca, solver acotado, agente de entorno.
7. **No añade.** No inventa cifras ni enlaces; un enlace solo entra si ya está en el README.
8. **Lo vetado no sobrevive.** Una frase que el validador estadístico vetó, o que cae en los
   [vetos obligatorios](../../CONTRIBUTING.md#revisión-de-un-texto-público), no queda en el texto
   reescrito, ni entera ni parafraseada.
9. **No completa.** Un texto cortado se revisa hasta donde llega; lo que falta no se rellena. No añade
   hashtags nuevos.
10. **Borrador de debate.** Lo que un artículo propone como pregunta se marca «pregunta abierta», no
    arquitectura del repositorio.
11. **Veto.** Se veta el texto que omite un resultado negativo pertinente, que presenta lo previsto como
    hecho o que usa una palabra vetada. El redactor entrega el texto al validador; sin su firma no hay
    visto bueno.

## Informe

Veredicto (apto, apto con cambios o no publicar), las frases vetadas con su motivo y, si se pidió, el
texto reescrito con su número de caracteres.
