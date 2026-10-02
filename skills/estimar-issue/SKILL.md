---
name: estimar-issue
description: Estimar un issue y registrar la estimación antes de que empiece el trabajo.
---

# Estimar un issue

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. La fuente de verdad es el flujo de `CONTRIBUTING.md`; esta skill solo lo proyecta.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md), *Flujo por issue*, paso 1 (ESTIMAR) y *Reglas del registro*.
- [`learning/README.md`](../../learning/README.md), *Bloques opcionales: `estimate` y `outcome`*.
- Política de tallas y modelos: [`docs/estimation.md`](../../docs/estimation.md).
- Episodio: `learning/episodes/036-issue-77.json`.

## Cuándo

Rol **orquestador** ([`agentes.md`](../../docs/entorno/agentes.md)): antes de que el implementador pase la
tarjeta a *In Progress* y antes de crear su rama o subagente.

## Procedimiento

1. Puntúa alcance, incertidumbre, riesgo y verificación con [`docs/estimation.md`](../../docs/estimation.md)
   y obtén la talla, los puntos y el modelo previsto con su esfuerzo. Los puntos son tamaño relativo, no
   horas ni tokens.
2. Escribe en el cuerpo del issue la sección **«Estimación v1 (fecha)»** con la talla, los puntos, la
   incertidumbre, el riesgo, el modelo previsto y el esfuerzo. Si la suma de factores y una comparación
   con un issue ancla discrepan, registra la discrepancia.
3. Rellena en el Project #5 los campos *Talla*, *Puntos*, *Incertidumbre*, *Riesgo* y *Modelo*. *Modelo*
   es el modelo **previsto**.
4. Delega con el ID y el esfuerzo previstos ([`enrutamiento.md`](../../docs/entorno/enrutamiento.md)).
5. Si después cambia el alcance, añade un comentario **«Estimación v2»** con fecha, motivo y evidencia. La
   v1 no se reescribe y *Modelo* no se sobrescribe, tampoco al escalar.
6. Un issue que necesita subissues se convierte en épica y deja de estimarse
   ([jerarquía](../../CONTRIBUTING.md#jerarquía-épica-issue-tareas)).
