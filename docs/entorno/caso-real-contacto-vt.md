# Caso real: supervisión del formulario de VinculaTerritorio

Registro observacional al 2026-09-30. Población: **agentes de entorno**. No es una campaña del agente de biblioteca ni del solver acotado y no incorpora datos a `evidence/` o `results/` del harness de experimento.

## Fuentes y límites

- [Cierre técnico 4332180](https://github.com/vinculaterritorio/vt-landing/commit/43321807c8bf5e0a0e8953a7ffad18bcbbb9e336): validación antes de proveedores, diagnóstico seguro y pruebas del SDK con red simulada.
- [Revisión independiente de #5](https://github.com/vinculaterritorio/vt-landing/issues/5#issuecomment-5912714397): el cierre anterior registró 133 pruebas de contacto y 49 de bitácora, lint y build. Son comprobaciones de ingeniería, no métricas de aprendizaje; no se repitieron para redactar este caso. En producción se comprobó GET 405 y rechazo 400 de un campo con salto de línea antes de proveedores, sin enviar correo. El supervisor no comprobó el buzón: delivered y recepción en inbox son observaciones distintas.
- [Project de landing #2](https://github.com/users/vinculaterritorio/projects/2): consulta de esta sesión, 10 tarjetas; 7 Done y 3 Todo. Siguen abiertos #4 (legal), #7 (SEO) y #18 (DMARC). El PR #19 de DMARC ya se integró mientras se escribía este documento; integrar código listo para aplicar no acredita que el DNS se haya corregido.
- [Project de este repositorio #5](https://github.com/users/cherrera0001/projects/5): 36 tarjetas Done y ningún issue abierto al consultarlo con su propietario. No confundir tableros ni IDs locales L-ISSUE con números de GitHub.

Hay un proceso auditable de corrección, comprobación independiente y despliegue. No hay ablación de memoria, control pareado, asignación aleatoria ni medición de contaminación entre contextos. No se calcula LearningGain o MemoryUtilityRate ni se demuestra la combinación histórica de variables, claves y despliegues que causó el fallo inicial.

La documentación de la landing llegó a afirmar que el repositorio no existía a partir de un 404. En esta sesión, leer el Project #5 también falló con la identidad de VinculaTerritorio y funcionó con la de su propietario, sin cambiar la cuenta activa persistente. Comprobar identidad y permisos antes de interpretar una respuesta de acceso.

[H7](../results/failure-transfer.md) conserva su conclusión controlada: «contamina» sobre su base C. Este caso no la sustituye. Una skill de entorno cambia el contrato de trabajo, no el algoritmo ni el modelo de la sesión. El ID del modelo de construcción se aplica al crear el subagente. Task Ledger sigue siendo la aplicación del Experimento 1.

## Un plan de continuación

1. Mantener el trabajo operativo en los issues existentes de la landing. Registrar verificaciones nuevas con fecha, origen y salida; cerrar tarjetas contra sus criterios. No simular decisiones legales, Search Console o DNS resueltos.
2. Antes del próximo incidente, registrar contexto, señal disponible, lección recuperada, acción propuesta y criterio de éxito. Después enlazar acción ejecutada, comprobación y fallos, conservando versiones previas.
3. Comparar incidentes compatibles con un control declarado antes de medir. Sin control, publicar procedencia e influencia observada, sin atribuir aprendizaje. Separar el campo de las campañas del harness de experimento.

Talla documental S: A2 + I1 + R2 + V1 = 6, 2 puntos. No crea versión, milestone ni protocolo experimental.
