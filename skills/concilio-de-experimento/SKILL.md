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
  experimento con modelo*, pasos 1 y 4 a 7: el procedimiento que esta skill proyecta.
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
2. **Convoca la primera ronda en paralelo, sobre los mismos archivos.** Ninguno modifica el
   repositorio, la evidencia ni un sistema externo; ejecutan solo en local. Siempre: analista de datos
   y forense del arnés. El auditor del método va en todas las vueltas, pero entra después de la
   revisión cruzada (paso 5). Según la pregunta: QA de trayectorias (si se propone
   cambiar la conducta del agente), arquitecto de IA (si se propone cambiar el modelo, el presupuesto o el
   cómputo, o adoptar un método ajeno) e inteligencia pública (si el experimento se mide en un sistema
   externo).
3. **Da a cada rol los archivos, no tu conclusión.** El encargo dice la pregunta, las rutas, las
   prohibiciones y la carpeta de trabajo. Un rol al que se le entrega la hipótesis la devuelve confirmada.
   Todos reciben la misma pregunta, la del dueño, además de la parte de su oficio, y una duda final: la
   pregunta que el dueño haría y que ningún documento contesta. El encargo no lleva cifras.
4. **Cada rol entrega** lo medido, lo inferido y lo no medido por separado, qué refutaría su conclusión,
   la lista de eventos de fallo que no dejaron rastro y un parecer corto para la bitácora.
5. **Revisión cruzada, siempre y sin que nadie la pida.** Arma un expediente con los informes sin firma
   (quita la línea que nombra el rol y la ruta de su carpeta) y reanuda a cada rol con su contexto. Cada uno
   entrega, con formato fijo y corto: qué mide bien cada otro informe, qué refuta con su número, qué se le
   pasó, qué retira de lo suyo, qué veta y su orden de las acciones candidatas. Después, y no antes, entra el
   auditor del método, con todo a la vista, y vuelve a contar las cifras de las que dependa
   una decisión. No se promedian los órdenes; los desacuerdos se anotan con el dato que los cerraría. Si
   falta la respuesta cruzada de un rol, no escribas decisiones. Una pregunta nueva del dueño a mitad del
   concilio va a todos los roles, no solo al auditor. Antes de cualquier subida, un rol escribe las
   predicciones fechadas; no las escribe el orquestador.
6. **Registra.** El orquestador copia el parecer de cada rol tal cual en la bitácora del experimento,
   junto con lo que cada uno retiró y sus propios fallos de la vuelta. Los roles no escriben en ella.
7. **Si el relato ya se corrigió a sí mismo**, o si la decisión cuesta dinero, cuota o un envío, encarga
   al verificador limpio que vuelva a medir las afirmaciones, entregadas como frases sin cifras. Hace su
   propio rescate; si su recuento difiere del relato, vale el suyo y se anota la diferencia.
8. **Después: decide con el dueño y deja el episodio.** El concilio va antes de preguntar; la decisión de
   subir, enviar o pagar es del dueño. La vuelta deja un episodio en `learning/episodes/` el mismo día
   (skill [`registrar-episodio`](../registrar-episodio/SKILL.md)). Antes de cerrar, pasa por el registro de
   hallazgos (`experiments/gemma_developer_agent/hallazgos.json`): un hallazgo medido no puede aparecer en
   dos vueltas sin una decisión escrita; cada uno pasa a `decidido` o `descartado`, o el registro dice por
   qué sigue abierto ([regla](../../CONTRIBUTING.md#vuelta-de-un-experimento-con-modelo), paso 8).

## Qué no hace

- No decide por el dueño ni sube, envía o contrata nada.
- No sustituye la revisión independiente de un PR ([revisor](../../docs/entorno/agentes.md#revisor)).
- No convierte la suma de opiniones en una medición: un voto unánime sobre un dato sin medir sigue sin
  medir. Si todos los roles son el mismo modelo, quitar las firmas evita la deferencia al rol y no da la
  diversidad de varios modelos; la bitácora lo dice.
