---
name: recall-antes-de-issue
description: Consultar la memoria de desarrollo del repositorio antes de implementar un issue.
---

# Recall antes de un issue

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**: no existe en ningún grafo ni se promociona desde lecciones.

## Fuente

- [`learning/README.md`](../../learning/README.md), sección *Flujo por issue*, paso 1 (RETRIEVE).
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md), *Flujo por issue*, paso 1.
- Episodios: `learning/episodes/012-issue-9.json` («Cuando el canal léxico no encuentra nada, el semántico
  puede recuperar lecciones transferibles: consultar ambos al empezar un issue») y
  `learning/episodes/013-issue-7.json`.

## Cuándo

Antes de escribir código para un issue, al empezar el trabajo del rol **implementador**
([`agentes.md`](../../docs/entorno/agentes.md)).

## Procedimiento

1. Ejecuta el recall léxico con el título del issue:

   ```bash
   python -m scripts.devlog recall "<título del issue>"
   ```

2. Si tienes el extra `[embeddings]`, repite con el canal semántico:

   ```bash
   python -m scripts.devlog recall "<título del issue>" --embedder fastembed
   ```

3. Lee las lecciones recuperadas **antes** de elegir herramientas o enfoque. Las acciones con valencia
   negativa indican pasos que ya fallaron en contextos parecidos.
4. Lee la sección «Issues parecidos»: cómo se estimó cada uno y cómo salió (talla, modelo previsto y usado,
   si escaló, PR, pasos fallidos). Si un issue parecido escaló o necesitó más de un PR, dilo al orquestador
   antes de empezar: puede cambiar la estimación. Con una instantánea del tablero a mano, añade
   `--snapshot <directorio>` para ver también su estado y su verificación.

Esta skill no escribe nada: `recall` reconstruye el grafo en memoria desde `learning/episodes/` y no lee
`learning/dev_memory.json`, que no se versiona y puede no existir en tu checkout.
