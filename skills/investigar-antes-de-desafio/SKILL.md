---
name: investigar-antes-de-desafio
description: Ante un desafío nuevo, buscar en la biblioteca local y en el código, abrir lo que falta, marcar el hueco y proponer al concilio un contraste que se pueda falsar, antes de experimentar.
---

# Investigar antes de un desafío

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria** ni una skill de memoria: no toca el esquema `software-learning-memory/v1`. La usa el
> investigador de fuentes, un agente de entorno: no es el agente de biblioteca ni el solver acotado.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#investigación-antes-del-experimento), *Investigación antes
  del experimento*: el orden que esta skill proyecta. Si esta skill y esa sección divergen, vale la
  sección.
- [`investigacion/README.md`](../../investigacion/README.md): el esquema de una ficha y cómo se busca.
- [`docs/entorno/agentes.md`](../../docs/entorno/agentes.md#investigador-de-fuentes): el rol y sus límites.
- Episodio: ninguno registra este procedimiento como lección.

## Cuándo

Antes de experimentar con un método que el repositorio no ha medido, y cuando un fallo no tiene un
mecanismo conocido. En una vuelta de un experimento con modelo, antes del diseñador del agente; no en la
primera ronda de medición.

## Procedimiento

1. **Busca.** Con Grep, en `investigacion/fuentes/indice.jsonl` (una línea por fuente) y en el código. Si
   el código ya nombra el mecanismo, dilo y para: la cita la hace el
   [investigador de papers](../investigador-papers/SKILL.md).
2. **Abre.** La obra por su DOI, su identificador de arXiv o la URL del editor; el video por su título, su
   descripción y, si la página la da, su transcripción. Autor, año y título se copian del registro (arXiv
   o Crossref), no de memoria. Lo que no abre no se cita: su ficha queda `no_abierto` con el motivo. No
   se pega una transcripción entera.
3. **Clasifica** cada ficha como biblioteca u océano, con la definición de la fuente. Una cifra de un
   paper o de un video es de su autor.
4. **Propón al concilio** un parecer de una página: mecanismo, ficha, si el código lo nombra, qué
   medición de este repositorio lo toca y un solo contraste con el resultado que lo descartaría. Sin
   diseño de corrida y sin subida.
5. **Entrega y para.** El experimento viene después y sigue
   [`specs/software_learning_protocol.md`](../../specs/software_learning_protocol.md),
   [`specs/loop_protocol.md`](../../specs/loop_protocol.md) y la skill
   [`concilio-de-experimento`](../concilio-de-experimento/SKILL.md).

## Qué no hace

- No edita el repositorio ni hace commit: escribe en la carpeta de trabajo que le den, y un implementador
  lleva las fichas al área por PR.
- No publica, no inicia sesión en un sistema externo y no recoge datos personales.
- No diseña la corrida, no escribe predicciones y no vota en el concilio.
- No lee `benchmark/private/` ni toca el harness de experimento.
