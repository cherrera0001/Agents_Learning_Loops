# Caso real: supervisión del sitio público de VinculaTerritorio

Registro observacional al 2026-09-30 sobre `vinculaterritorio.cl` (repositorio `vinculaterritorio/vt-landing`).
Población: **agentes de entorno**, que recuperan memoria, comprueban producción y cierran o bloquean issues. No
es una campaña del agente de biblioteca ni del solver acotado, no usa el grafo del Experimento 1 y no incorpora
datos a `evidence/` ni a `results/` del harness de experimento. Task Ledger sigue siendo la aplicación del
Experimento 1.

## Fuentes y límites

Leídas en la versión publicada de la landing (`origin/master`, `2293fbb`):

- `AGENTS.md`, `PENDIENTES.md` y `docs/agent-memory/runs/issue-7-verificacion-post-despliegue.run.json`.
- El recibo de cierre del formulario que cita `PENDIENTES.md`:
  [`contacto-cierre-integrado.run.json`](https://github.com/vinculaterritorio/vt-landing/blob/master/docs/agent-memory/runs/contacto-cierre-integrado.run.json).
- [Cierre técnico 4332180](https://github.com/vinculaterritorio/vt-landing/commit/43321807c8bf5e0a0e8953a7ffad18bcbbb9e336)
  y la [revisión independiente de #5](https://github.com/vinculaterritorio/vt-landing/issues/5#issuecomment-5912714397):
  133 pruebas de contacto y 49 de bitácora, lint y build. Son comprobaciones de ingeniería, no métricas de
  aprendizaje, y no se repitieron para redactar este caso.
- [Project de la landing #2](https://github.com/users/vinculaterritorio/projects/2), consultado el 2026-09-30:
  7 Done, 1 In Progress y 2 Todo. Siguen abiertos #4 (legal), #7 (SEO) y #18 (DMARC).
- [Project de este repositorio #5](https://github.com/users/cherrera0001/projects/5). No confundir tableros ni
  IDs locales L-ISSUE con números de GitHub.

**No publicadas.** Las skills de la landing `.cursor/skills/resolver-issue/SKILL.md` y
`.cursor/skills/verificacion-seo-produccion/SKILL.md` existen solo como archivos locales sin seguimiento en una
copia de trabajo, no en `origin/master`. Este caso no las cita como fuente ni describe su contenido. La única
skill publicada es `.cursor/skills/revisor-privacidad-21719/SKILL.md`.

Hay un proceso auditable de corrección, comprobación independiente y despliegue. No hay ablación de memoria,
control pareado, asignación aleatoria ni medición de contaminación entre contextos. No se calcula LearningGain o
MemoryUtilityRate ni se demuestra la combinación histórica de variables, claves y despliegues que causó el fallo
inicial.

## Formulario de contacto (#5, cerrado)

- `pages/api/contacto.ts` es la API: no hay backend aparte.
- Primero respondía **503** (sin `RESEND_API_KEY`). Después respondió **502** con «No se pudo enviar el correo»,
  porque Resend rechazó la clave que tenía Vercel. Los tamaños de respuesta de 44 y 39 bytes se observaron en la
  sesión de diagnóstico y no figuran en los recibos de la landing.
- El dueño rotó la clave en Vercel Production y redesplegó. El formulario respondió **200**, y Resend registra el
  mensaje `01a0f254…` a `contacto@vinculaterritorio.cl` con `last_event: delivered`. Lo **informó el supervisor**
  con una consulta de solo lectura; la sesión que escribió el recibo no lo verificó por su cuenta.
- `delivered` solo dice que el servidor de correo aceptó el mensaje. La llegada a la bandeja de entrada es un
  **reporte del dueño**, no una medición, y no se leyeron los resultados DKIM/DMARC de las cabeceras.
- La causa exacta del 502 anterior no está establecida, porque no hay logs de Production de ese momento.

## Verificación post-despliegue (#7, abierto)

- `yarn check:produccion` sale con exit 0 contra producción: `www` → apex con 308, `sitemap.xml` con las 4 URL
  indexables, `/pricing` y `/privacy` rastreables y con `noindex`, `Organization` en las indexables, `security.txt`
  y `og.png`.
- El LCP móvil de la portada se midió **en laboratorio** (Lighthouse con Chrome local): 4,4 s. No hay datos de campo.
- `FAQPage` no se repone: el rediseño del 2026-09-24 quitó la sección visible de preguntas.
- **Sin hacer, y del dueño:** en Search Console, verificar la propiedad, enviar el sitemap, inspeccionar las
  4 URL, confirmar «Excluida por etiqueta noindex» y probar los resultados enriquecidos de `Organization`.

## Roles de la landing

| Rol | Estado | Qué hace según lo publicado |
|---|---|---|
| Resolver un issue | skill en borrador local, **no publicada** | — |
| Verificador SEO | skill en borrador local, **no publicada** | La comprobación publicada es `yarn check:produccion` (`scripts/check-produccion-seo.mjs`) |
| Revisor de privacidad | skill publicada (`revisor-privacidad-21719`) | Revisión frente a la Ley 21.719; no sustituye al abogado del #4 |

**Regla de cierre**, adoptada en este repositorio en [`agentes.md`](agentes.md) (*Cierre*): un issue se cierra o se
bloquea en el dueño con la etiqueta `human-decision`, y queda prohibido dejarlo en Todo después de una
comprobación en exit 0. En la landing, hoy #7 y #18 siguen abiertos **sin** esa etiqueta, aunque lo que falta en
los dos es del dueño (Search Console y el token de Cloudflare).

## Qué se sabe y con qué fuerza

| Categoría | Contenido |
|---|---|
| **Implementado** en la landing | API `pages/api/contacto.ts` con diagnóstico `code` y `reference`; `yarn check:produccion`; `cf-dmarc.sh` y `yarn check:dmarc` (PR #19); memoria en `docs/agent-memory/` con recuperación, control y recibos sellados |
| **Observado** en producción | 200 del formulario y `delivered` en Resend (informados por el supervisor); `check:produccion` en exit 0; 2 registros DMARC en el DNS (hoy, `check:dmarc` sale con exit 1); LCP móvil de 4,4 s en laboratorio |
| **Inferido** | La causa del 502 fue de configuración: la rotación de la clave lo respalda, pero no lo prueba. En #18, la memoria recuperada cambió la primera acción frente a la línea de control (buzón `rua` y quién decide la política) |
| **Hipotético** | Que esa memoria mejore resultados; que el procedimiento de cierre evite issues olvidados; la bandeja frente al spam medida, no reportada |

La documentación de la landing llegó a afirmar que el repositorio no existía a partir de un 404. En esta sesión,
leer el Project #5 también falló con la identidad de VinculaTerritorio y funcionó con la de su propietario, sin
cambiar la cuenta activa persistente. Comprobar identidad y permisos antes de interpretar una respuesta de acceso.

[H4](../results/h4-associative-vs-history.md) sigue en pie: en el laboratorio, la memoria asociativa no superó al
historial textual. [H7](../results/failure-transfer.md) conserva su conclusión controlada: «contamina» sobre su
base C. Este caso no sustituye ninguna de las dos. Una skill de entorno cambia el contrato de trabajo, no el
algoritmo ni el modelo de la sesión. El ID del modelo de construcción se aplica al crear el subagente.

## Un plan de continuación

1. Mantener el trabajo operativo en los issues existentes de la landing. Registrar verificaciones nuevas con fecha,
   origen y salida; cerrar tarjetas contra sus criterios. No simular decisiones legales, Search Console o DNS
   resueltos.
2. Antes del próximo incidente, registrar contexto, señal disponible, lección recuperada, acción propuesta y
   criterio de éxito. Después enlazar acción ejecutada, comprobación y fallos, conservando versiones previas.
3. Comparar incidentes compatibles con un control declarado antes de medir. Sin control, publicar procedencia e
   influencia observada, sin atribuir aprendizaje. Separar el campo de las campañas del harness de experimento.

Talla documental S: A2 + I1 + R2 + V1 = 6, 2 puntos. No crea versión, milestone ni protocolo experimental.
