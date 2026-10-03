---
name: registrar-episodio
description: Registrar un issue como episodio de la bitácora con los fallos tal como ocurrieron.
---

# Registrar un episodio

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Los episodios de `learning/episodes/` son la fuente de verdad; esta skill solo describe
> cómo escribirlos.

## Fuente

- [`learning/README.md`](../../learning/README.md), secciones *Formato de un episodio*, *Reglas de
  registro* y *Vocabulario de acciones*.
- Episodio: `learning/episodes/004-issue-13.json` («Registrar el fallo en la acción que lo causó, no en la
  que lo detectó» y «Solo el primer éxito tras un fallo es su resolución»).

## Cuándo

Al terminar un issue, antes de abrir el PR. El episodio viaja en el mismo PR que el cambio.

## Procedimiento

1. Crea `learning/episodes/NNN-<id>.json`. `seq` continúa la numeración: **`seq` ordena el reloj lógico**
   de la memoria. Comprueba el último `seq` libre en `origin/main` (`git ls-tree origin/main learning/episodes/`)
   y en los PR abiertos (`gh pr list --state open --json number,files`), no solo en tu rama: dos PR
   paralelos pueden tomar el mismo número.
2. Anota cada paso con una acción del vocabulario de `learning/README.md`, indicando `success` y un
   `error` o una `note`.
3. **El fallo va en la acción que lo causó, no en la que lo detectó.** Si una revisión encuentra un test
   defectuoso, falla `write_tests` y `review_code` es un éxito.
4. **El primer éxito posterior a un fallo es su resolución.** Ordena los pasos para que eso sea cierto: la
   consolidación crea `error -RESOLVED_BY-> acción` solo para ese paso.
5. Registra los fallos **tal como ocurrieron**, sin suavizarlos ni omitirlos.
6. Escribe las lecciones como frases accionables.
7. **No entregues la memoria derivada.** `learning/dev_memory.json` no se versiona (está en
   `.gitignore`; motivo en `learning/README.md`): el PR lleva solo el episodio. Para comprobar que el
   episodio se consolida, `python -m scripts.devlog rebuild` escribe una copia local, que no se commitea ni
   se edita a mano.
