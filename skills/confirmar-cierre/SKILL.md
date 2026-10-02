---
name: confirmar-cierre
description: Confirmar el criterio de cierre de un issue antes de moverlo a Done.
---

# Confirmar el cierre de un issue

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. La fuente de verdad es el flujo de `CONTRIBUTING.md`; esta skill solo lo proyecta.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md), *Flujo por issue*, paso 7 (CONFIRMAR) y paso 8 (*Done*).
- [`docs/entorno/harness.md`](../../docs/entorno/harness.md), *Criterios de cierre por tipo de trabajo*.
- [`learning/README.md`](../../learning/README.md), bloque `outcome` (la verificación no va en el episodio).
- Episodio: `learning/episodes/036-issue-77.json`.

## Cuándo

Rol **orquestador** ([`agentes.md`](../../docs/entorno/agentes.md)): después de que el PR esté mergeado y
antes de mover la tarjeta a *Done*. En el Project #5, *Done* cierra el issue automáticamente.

## Procedimiento

1. Verifica `mergedAt` del PR. Sin merge verificado no se confirma nada.
2. Identifica el *Tipo de cierre* del issue y comprueba su criterio con la tabla de `harness.md`
   (código y docs: CI verde en main; experimento: recibos, verificación independiente y lectura
   publicada; sistema externo: observación real con comando y fecha).
3. Enlaza la evidencia en un comentario del issue y pon *Verificación* = *Verificada* en el tablero. Si la
   comprobación falla, *Verificación* = *Fallida* y el issue sigue abierto. Si es de sistema externo y falta
   la observación, *Verificación* = *Pendiente*, el issue sigue abierto y el PR usó `Refs`.
4. Registra *Modelo usado* y *Escaló* en el tablero. Sin transcripción, *Modelo usado* es autoinformado y no
   se presenta como medido. *Modelo* (el previsto) no se toca.
5. Solo con *Verificación* = *Verificada*, mueve la tarjeta a *Done*.
6. Si el issue es hijo de una épica, esta se cierra cuando todos sus hijos obligatorios están cerrados y sus
   criterios propios cumplidos.
