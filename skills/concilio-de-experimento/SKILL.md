---
name: concilio-de-experimento
description: Pasar cada vuelta de un experimento con modelo por roles independientes en solo lectura antes de proponer un cambio, y registrar su parecer.
---

# Concilio de experimento

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. La usa el orquestador con el staff de experimento: ningún rol es el agente de biblioteca
> ni el solver acotado.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#vuelta-de-un-experimento-con-modelo), *Vuelta de un
  experimento con modelo*: el procedimiento que esta skill proyecta.
- [`docs/entorno/agentes.md`](../../docs/entorno/agentes.md#staff-de-experimento): los siete roles.
- [`skills/corrida-valida`](../corrida-valida/SKILL.md): el criterio que el concilio aplica.
- Episodios: `learning/episodes/064-issue-103-estado-medido-y-ciclo-kaggle.json` («cuando dos roles de un
  concilio recomiendan cosas opuestas, busca en el informe de uno la medida que el otro dejó sin verse») y
  `learning/episodes/065-issue-103-vuelta-39-concilio-y-registro.json` (una sola sesión afirmó de más
  cuatro veces; el concilio lo corrigió y cada rol retiró lo suyo).

## Cuándo

Rol **orquestador**: en cada vuelta de un experimento con modelo, después de bajar los datos y antes de
proponer un cambio al dueño. Y de inmediato, sin esperar a que nadie lo pida, cuando una corrida o un
envío falla sin explicación.

## Procedimiento

1. **Antes: recall y rescate.** Ejecuta `devlog recall` con la pregunta de la vuelta desde una rama al
   día con `origin/main`, y baja los datos con la skill [`corrida-valida`](../corrida-valida/SKILL.md).
   Sin rescate demostrado no hay concilio.
2. **Convoca los roles en paralelo y en solo lectura, sobre los mismos archivos.** Siempre: analista de
   datos, forense del arnés y auditor del método. Según la pregunta: QA de trayectorias (si se propone
   cambiar la conducta del agente), arquitecto de IA (si se propone cambiar el modelo, el presupuesto o el
   cómputo, o adoptar un método ajeno) e inteligencia pública (si el experimento se mide en un sistema
   externo).
3. **Da a cada rol los archivos, no tu conclusión.** El encargo dice la pregunta, las rutas, las
   prohibiciones y la carpeta de trabajo. Un rol al que se le entrega la hipótesis la devuelve confirmada.
4. **Cada rol entrega** lo medido, lo inferido y lo no medido por separado, qué refutaría su conclusión, y
   un parecer corto para la bitácora.
5. **Cruza los informes.** Busca en cada uno la medida que otro dejó «sin verse». Cuando llegue un hecho
   nuevo, vuelve a preguntar a cada rol qué afirmación suya se cae. Los desacuerdos se anotan con el dato
   que los cerraría; no se promedian.
6. **Registra.** El orquestador copia el parecer de cada rol tal cual en la bitácora del experimento,
   junto con lo que cada uno retiró y sus propios fallos de la vuelta. Los roles no escriben en ella.
7. **Si el relato ya se corrigió a sí mismo**, o si la decisión cuesta dinero, cuota o un envío, encarga
   al verificador limpio que vuelva a medir las afirmaciones, entregadas como frases sin cifras.
8. **Después: decide con el dueño y deja el episodio.** El concilio va antes de preguntar; la decisión de
   subir, enviar o pagar es del dueño. La vuelta deja un episodio en `learning/episodes/` el mismo día
   (skill [`registrar-episodio`](../registrar-episodio/SKILL.md)).

## Qué no hace

- No decide por el dueño ni sube, envía o contrata nada.
- No sustituye la revisión independiente de un PR ([revisor](../../docs/entorno/agentes.md#revisor)).
- No convierte la suma de opiniones en una medición: un voto unánime sobre un dato sin medir sigue sin
  medir.
