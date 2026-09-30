# Caso de campo: supervisión de agy/Gemini

Registro del 2026-09-30. Es un proceso real de **agentes de entorno**, con diagnóstico, encargo y comprobación posterior. No es una nueva campaña de los Experimentos 0 o 1, no cambia Task Ledger ni sus operadores y no incorpora datos a sus `evidence/` o `results/`. Una corrección operativa no demuestra aprendizaje causal sin control.

## Pregunta y alcance

El encargo del dueño fue ayudar a agy/Gemini CLI con dos focos, WIP=1: primero desbloquear la asistencia Gemini y después aportar valor territorial mediante métricas y matching. La pregunta comprobable del primer foco era si la configuración efectiva llega al proveedor real, obtiene salida válida y evita presentar mock como Gemini. El segundo requiere supresión small-N y recomendaciones justificadas, sin convertir matching en selección automática.

## Proceso observado

1. **Leer antes de intervenir.** Se leyeron PROMPT_NUBLE, PROMPT_CONCILIO, SESSION_STATE, catálogo/registro/adaptador y documentos de métricas, dimensiones y preguntas. Se confirmó el repositorio `vt-plataforma` y el Project oficial nº 1, con 232 tarjetas en ese corte. No se inició una segunda implementación ni se tocó `definicion/`.
2. **Separar configuración de autenticación.** El código daba precedencia a `ai_agent.provider/model` sobre `AI_PROVIDER/GEMINI_MODEL`; también intervenían `enabled`, kill switch, tier y aceptación de uso de datos. Cambiar sólo una variable no acreditaba el modelo efectivo. El diagnóstico leyó la clave local únicamente en memoria, sin registrarla: GET `/models` respondió 200 y enumeró `gemini-3.6-flash`. No se llamó a generateContent en esa supervisión. Autenticación local comprobada; cuota, catálogo vivo y despliegue seguían sin medirse.
3. **Ejecutar y conservar los bloqueos.** Las unitarias del adaptador pasaron 28/28. La ejecución conjunta tuvo 58 pruebas aprobadas y 9 fallos por `ECONNREFUSED` a PostgreSQL. Docker tampoco respondió en los dos contextos consultados. No se interpretó eso como defecto del proveedor. `verify:quick` pasó, pero su propia salida excluye tests de API, builds, SQL, navegador y OpenAPI.
4. **Corregir el método de supervisión.** La primera consulta de recall pasó texto sin `--text` y no generó queries; se repitió con el argumento requerido. La primera sonda `node -e` perdió comillas por el paso PowerShell→Node y falló antes de contactar a Google. Se trasladó el programa a un archivo temporal, manteniendo la clave fuera de argumentos; entonces se obtuvo el 200. Estos fueron fallos del supervisor, no del producto.
5. **Preparar el encargo corregido.** Se pidió conservar WIP=1, revisar el catálogo efectivo, separar pruebas offline de smoke real, no activar consentimiento o tier de pago por conveniencia, reutilizar #265/#281 y el módulo matching. Se registraron pruebas y NO MEDIDO en SESSION_STATE. No se obtuvo el ID de la conversación existente: no se afirma haber enviado la corrección por CLI a esa sesión. El texto quedó disponible en el repositorio.
6. **Revisar el avance posterior.** El commit [ffdc372](https://github.com/vinculaterritorio/vt-plataforma/commit/ffdc372cbb0b69e0a2090a4b31058549625bda00) añadió cambios de IA, matching y small-N y conservó el diagnóstico. En esta documentación se reejecutaron dos suites: **33 de IA y 11 de small-N, 44/44**, con salida archivada. Son pruebas offline; no acreditan producción ni el catálogo de la base.

## Qué informó agy y qué se comprobó

SESSION_STATE de ffdc372 declara generación HTTP 200 con cuatro sugerencias, agente habilitado, 10 pruebas small-N y resolución local completa. Se conserva como **informe del implementador**. La revisión posterior contó 11 pruebas small-N; los conteos pertenecen a cortes distintos y no se suman a las 28 anteriores.

La lectura de [smoke-gemini-live.mjs](https://github.com/vinculaterritorio/vt-plataforma/blob/ffdc372cbb0b69e0a2090a4b31058549625bda00/scripts/smoke-gemini-live.mjs) muestra una llamada fetch propia, sin ejecutar `AsistenteGemini` ni `obtenerAsistentePara`. Prueba un modelo alternativo ante 503/429 y sólo exige un array no vacío tras parsear JSON. Por ello su éxito no prueba el mismo modelo ni todas las guardas del adaptador de la aplicación. No se reejecutó ese smoke para esta documentación, no se enviaron datos territoriales y no se verificó el catálogo vivo. Leer una migración de seed tampoco demuestra el estado actual de una fila.

Las unitarias small-N comprueban ejemplos de supresión; no demuestran por sí solas resistencia a reconstrucción por totales, filtros o paginación. Una puntuación territorial determinista tampoco demuestra utilidad predictiva ni impacto atribuible. P-05/P-26/P-27 y las decisiones de privacidad mantienen su alcance humano.

## Evidencia conservada

La [copia local del recibo](evidencia/agy-gemini-20260930/recibo.json) conserva sus bytes y hashes. El [manifest](evidencia/agy-gemini-20260930/manifest.json) identifica origen, cortes y hashes de las copias y la revisión posterior. Los seis hashes originales se comprobaron antes de copiar. El recibo es de **entorno**, no un recibo del harness de experimento; SHA-256 detecta cambios de bytes, no acredita por sí solo autenticidad del resultado ni causalidad.

## Lecciones para el próximo ciclo

- Comprobar por separado autenticación, catálogo efectivo, generación validada, comportamiento del endpoint y producción. Cada prueba acredita sólo su capa.
- Hacer el smoke a través del mismo adaptador y resolución de catálogo que usa el producto; registrar proveedor y modelo realmente usados, sin secretos ni fallback oculto.
- Ante una falla de infraestructura, conservar el bloqueo y ejecutar sólo las comprobaciones independientes; no registrar una prueba unitaria verde como reparación de la base.
- Leer la interfaz del recall y evitar código inline con quoting ambiguo entre shells. Los errores de herramientas pertenecen al supervisor.
- Versionar los informes por SHA y distinguir informe, lectura de código y ejecución independiente. No sumar repeticiones o cortes como resultados nuevos.
- Mantener el contenido gratuito limitado al diagnóstico sintético autorizado; documentar una regla no concede consentimiento ni habilita datos reales.

Son reglas candidatas de trabajo, no skills de memoria promovidas ni ganancias de aprendizaje medidas. La siguiente comprobación operativa es obtener una salida validada mediante el adaptador real y el catálogo efectivo, conservando los negativos y el reporte de modelo; después verificar privacidad y matching contra sus criterios existentes. Sin ablación o control declarado previamente, el caso seguirá siendo observacional.

Talla documental S: A2 + I1 + R2 + V1 = 6, 2 puntos. Documento y bitácora escritos por Codex; no se atribuye ejecución a un modelo Claude. El Markdown no cambia el modelo de sesión.

## Consolidación de esta documentación

El episodio 034 registra este trabajo documental; `dev_memory.json` se reconstruye desde los episodios. Una consulta posterior recuperó las cuatro reglas nuevas ([salida](evidencia/agy-gemini-20260930/recall-despues.log)). La consulta se eligió después de escribirlas: demuestra accesibilidad en ese ejemplo, no utilidad, retención ni ganancia contra un control.

La [revisión posterior](evidencia/agy-gemini-20260930/revision-recibo.json) también se añadió a SESSION_STATE de la plataforma, sin reemplazar el informe previo ni alterar el código. En la validación documental, ruff pasó; mypy local no cargó una DLL bloqueada por Control de aplicaciones de Windows. Se conserva como bloqueo de entorno, no como error de tipos ni aprobación local. La CI del PR debe resolver la comprobación de tipos antes de cerrar.
