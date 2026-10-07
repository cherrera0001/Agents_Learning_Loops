---
name: revisar-manuscrito
description: Llevar un manuscrito con datos desde el borrador hasta una versión firmada y maquetada, con las comprobaciones mecánicas primero y los cinco roles del staff en el orden que evita repetir firmas.
---

# Revisar un manuscrito

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. Orquesta al staff de texto público; no sustituye a ninguno de sus roles.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#revisión-de-un-texto-público), *Revisión de un texto
  público*.
- Roles: [`auditor-datos`](../auditor-datos/SKILL.md), [`investigador-papers`](../investigador-papers/SKILL.md),
  [`revisor-figuras-tablas`](../revisor-figuras-tablas/SKILL.md), [`revisor-redactor`](../revisor-redactor/SKILL.md)
  y [`validador-estadistico`](../validador-estadistico/SKILL.md).
- Herramientas: [`scripts/paper_check.py`](../../scripts/paper_check.py) y
  [`scripts/paper_pdf.py`](../../scripts/paper_pdf.py).
- Episodio: `learning/episodes/063-issue-148-staff-datos-y-figuras.json`. El 2026-10-07 un manuscrito pasó
  por seis rondas de revisión en una noche: cada corrección dejaba sin firma la versión anterior, y la
  mitad de los hallazgos (citas numéricas, cifras del resumen sin respaldo, tablas sin nota, exceso de
  palabras, obras con versión publicada) los habría encontrado un guion en un segundo.

## Cuándo

Cada vez que un texto con datos va a salir del repositorio: un artículo, un informe de competición, un
resumen para un tercero.

## Procedimiento

El orden importa: lo mecánico antes que lo que cuesta, y la firma al final, una sola vez.

1. **Reglas del destino, leídas en su fuente.** Extensión, secciones obligatorias, idioma, estilo de citas,
   formato de entrega y fecha. Se anotan con la fecha de lectura. Lo que las reglas no dicen se pregunta
   al dueño; no se supone.
2. **Comprobación mecánica, sin agentes.**
   `python -m scripts.paper_check comprobar <manuscrito> --limite <palabras>`.
   No se convoca a nadie mientras tenga hallazgos.
3. **Referencias contra su registro.** `python -m scripts.paper_check referencias <manuscrito>`: año,
   autores, versión publicada y código de respuesta de cada enlace. Sus problemas se corrigen antes de la
   lectura del investigador.
4. **Auditor de datos**, solo: inventario de mediciones y vigencia. Si veta una afirmación de fondo, se
   reescribe antes de seguir; no tiene sentido pulir un texto cuya tesis ya no vale.
5. **En paralelo:** investigador de papers (atribuciones contra el resumen de cada obra), revisor de
   figuras y tablas, y revisor redactor (incluida la coherencia del resumen con el cuerpo).
6. **Una sola ronda de correcciones.** Se juntan los tres informes y se aplican de una vez. Si dos
   revisores se contradicen, decide la fuente: el dato crudo, el registro oficial o las reglas del destino.
7. **Comprobación mecánica otra vez** (pasos 2 y 3): las correcciones suelen romper el límite de palabras
   o la correspondencia entre citas y lista.
8. **Validador estadístico, al final.** Firma la versión exacta citando su SHA-256 y su conteo de
   caracteres. Si veta, se corrige y vuelve a leer solo él.
9. **Maquetación** con [`maquetar-apa`](../maquetar-apa/SKILL.md) si el destino acepta o pide PDF.
10. **Registro fechado** en `docs/entorno/`: huella firmada, veredictos, lo que no se pudo comprobar.
11. **Documentos de entrada al día.** Si la revisión cambió una cifra vigente, el README y el recorrido
    del caso se actualizan en el mismo paso.

## Encargo a cada revisor

Cada encargo es autocontenido y dice:

- la ruta del texto y la **huella** que se espera leer;
- las fuentes contra las que contrastar, con rutas;
- qué se entrega y en cuántas líneas, y que cada corrección va como «texto actual → texto corregido»;
- que el trabajo es de solo lectura;
- que separe lo verificado abriendo la fuente de lo inferido;
- la regla de confidencialidad que aplique (solo agregados; sin identificadores de tareas).

## Lo que no se hace

- Pedir una firma antes de terminar las correcciones de los demás roles.
- Dar por firmada una versión cuya huella no es la que el validador citó.
- Publicar, hacer commit o enviar: esta skill deja un texto firmado; publicar lo decide el dueño.

## Informe

- **Huella firmada**, conteo de palabras frente al límite y veredicto de cada rol.
- **Correcciones aplicadas** y **correcciones rechazadas**, con el motivo.
- **Lo que quedó sin comprobar** (texto completo de una obra, formato en el destino, enlaces que el editor
  bloquea).
