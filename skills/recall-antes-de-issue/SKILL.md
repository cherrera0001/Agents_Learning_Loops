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

Esta skill no escribe nada: solo lee `learning/dev_memory.json` (o lo reconstruye en memoria desde
`learning/episodes/` si falta).
