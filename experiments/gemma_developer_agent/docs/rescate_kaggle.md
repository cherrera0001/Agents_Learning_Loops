# Rescate de la información de Kaggle (#103, #106)

`scripts/kaggle_rescate.py` baja de una vez todo lo que la cuenta puede leer del concurso y lo deja en
disco, en una carpeta con la fecha y la hora UTC. Existe porque esa información se pierde: el log de un
notebook se sobrescribe con la versión siguiente y desaparece al borrar el notebook, y la tabla pública
cambia cada día.

Este documento dice cómo se usa y qué se leyó el 2026-10-04. Lleva solo agregados de la tabla pública y de
los envíos propios; no nombra equipos ni contiene datos de tareas.

## Comando

```bash
python -m scripts.kaggle_rescate --destino experiments/gemma_developer_agent/data/rescate_kaggle
python -m scripts.kaggle_rescate --destino <carpeta ya bajada> --sin-red     # solo resume
```

Lee el token de `KAGGLE_API_TOKEN`. Se niega si `--destino` queda versionable (`data/` está ignorado).

| Qué baja | Archivo |
|---|---|
| Todos los campos de cada envío propio | `envios.json` |
| La tabla pública completa | `tabla_publica.zip` |
| Por cada notebook propio: estado, metadatos, código, log y archivos de salida | `notebooks/<nombre>/` |

Imprime un resumen: los envíos propios y la tabla **en tareas**, el puesto propio, y cada notebook con su
estado, su versión y lo que dejó.

**La carpeta fechada la crea el guion.** `--destino` es la carpeta madre; si se le pasa una ya fechada,
queda una dentro de otra.

**Si algo falta, sigue.** Un notebook o un archivo de salida que no se pueda bajar o guardar no detiene el
resto: queda en `faltantes.json`, el resumen lo repite en `descarga_incompleta` y el guion sale con 4. Un
archivo de salida cuyo nombre no cabe en una ruta de Windows se guarda acortado, con una huella; su nombre
en Kaggle queda en `notebooks/<nombre>/salidas.json`. El 2026-10-06 un nombre así cortó la descarga a
mitad de la lista y dejó cuatro notebooks sin bajar.

**Lo que no puede bajar.** El archivo que Kaggle guarda de cada envío (la API responde 401 a esa ruta) y
los logs de notebooks ya borrados. De esos solo queda lo que se haya guardado antes.

## Cómo se lee la tabla

La nota de la tabla es `k/n` **truncado** a dos decimales, no redondeado. Con las notas observadas el
2026-10-04, los tamaños compatibles son 58, 79, 86 y 89; 58 coincide con lo que se dice en el foro. Con
`n = 58`:

| Nota | 0,01 | 0,03 | 0,05 | 0,06 | 0,08 | 0,10 | 0,12 | 0,13 | 0,15 | 0,17 | 0,24 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Tareas | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 14 |

La nota 0,06 del envío 56808559 son **4 tareas**, no «3 o 4».

## Lectura del 2026-10-04, 16:28 UTC

**La tabla, en tareas** (1 683 equipos; se muestra la mejor nota de cada equipo):

| Tareas | 14 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Equipos | 1 | 5 | 37 | 119 | 274 | 339 | 314 | 197 | 150 | 63 | 53 | 131 |

- Mediana 5 tareas, media 4,92, desviación 2,28.
- Una binomial con esa misma media sobre 58 tareas tendría desviación 2,12. La dispersión de toda la
  tabla es casi la que daría un solo agente repetido muchas veces.
- El envío propio: 4 tareas, puesto 1 277, con un envío. 1 089 equipos tienen más tareas.

**La nota sube con el número de envíos**, y sube menos de lo que subiría por solo elegir el mejor:

| Envíos del equipo | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| Media de tareas observada | 3,83 | 4,49 | 4,85 | 5,32 | 5,70 | 5,97 | 5,91 |
| Mejor de m envíos iguales (binomial, p = 3,83/58) | 3,83 | 4,88 | 5,45 | 5,83 | 6,12 | 6,34 | 6,53 |

- Un equipo con un solo envío tiene de media 3,83 tareas. El envío propio, con 4, es el resultado
  típico de un primer envío.
- El modelo binomial trata las tareas como independientes y de igual dificultad. No lo son: muchas
  fallan siempre. El ruido real entre reenvíos es menor que el binomial, y por eso lo observado queda por
  debajo de la fila esperada. Aun así, el patrón dice que buena parte de la diferencia entre equipos se
  explica por haber enviado más veces.
- Solo el primer puesto (14 tareas) queda fuera de lo que ese ruido produce.

**Qué no dice esta lectura.** No mide el ruido de reenviar un mismo zip: eso exige reenviarlo. Tampoco
dice qué configuración usan los equipos de arriba.

## Lectura del 2026-10-06, 19:10 UTC

Descarga completa: 12 notebooks, ninguno faltante. Carpeta `data/rescate_kaggle/2026-10-06T1910Z/`.

**Envíos propios.** Son dos, del mismo zip (`registry.json`, `sub-002` y `sub-003`):

| Ref. Kaggle | Enviado (UTC) | Estado | Nota | Tareas con n = 58 | Bytes que guarda Kaggle |
|---|---|---|---|---|---|
| 56808559 | 2026-10-03 23:46 | complete | 0,06 | 4 | 86 883 |
| 56830336 | 2026-10-04 17:41 | complete | 0,05 | 3 | 72 047 |

- El mismo zip dio 4 y 3: una tarea de diferencia entre dos envíos iguales. La mejor nota no cambió.
- El zip local pesa 3 495 bytes. Kaggle guarda otro tamaño, distinto en cada envío, y la API no deja bajar
  ese archivo: su identidad con el zip local no está comprobada.
- Los dos zips locales compilan con `adk-submission` (`python -m scripts.kaggle_submission verify`, salida
  0). El compilador no está en el `.venv` del repositorio, donde `verify` sale con 3: hay que correrlo
  con el entorno del arnés.

**El tamaño de la tabla.** Con las notas de hoy son compatibles 58, 79, 86 y todos los tamaños desde 90.
El resumen usa el menor y ahora lo dice en `tamano_de_tabla_usado`. Las tareas de cada nota valen si la
tabla tiene 58.

**La tabla, en tareas** (1 935 equipos):

| Tareas | 14 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Equipos | 1 | 3 | 14 | 64 | 218 | 367 | 366 | 324 | 189 | 137 | 73 | 48 | 131 |

- Mediana 6 tareas (era 5), media 5,30, desviación 2,34; la binomial con esa media daría 2,19.
- El envío propio: 4 tareas, puesto 1 503, con dos envíos. 1 357 equipos tienen más tareas.
- Media con un envío: 3,94 tareas (449 equipos); con dos: 4,56 (364 equipos).

**Notebooks.** Once terminados y `iteracion-04` en ejecución, sin log todavía. Los dos
`new-benchmark-task-*` son de otro benchmark y de otro modelo: no cuentan para este experimento.

**Sin medir.** Sesiones activas y cuota de GPU: exigen la sesión web del dueño.

## Lo que había en los logs y no se había usado

De las corridas del 2026-10-03 y 04 (los de la GPU están en `data/ensayo_kaggle/`, bajados antes de
borrar el notebook):

| Dato | Valor | Fuente |
|---|---|---|
| Máquina con L4×4 | 48 CPU, 193 GB de RAM, 4 GPU de 23 034 MiB | Sondas `cpu`, `memoria` y `gpu` |
| Máquina sin GPU | 4 CPU, 32 GB de RAM | Ídem |
| Disposición de entrada en corridas por API | `competitions/`, `datasets/<dueño>/`, `models/` | Log, en las cuatro corridas |
| Ruedas instaladas | 41, en la ruta por lotes | Log, en las cuatro corridas |
| Compilación del kit | 30 a 36 s | Sonda `compila` |
| El servidor del modelo cayó | A los 62 s con T4×2; a los 474 s y 753 s con L4×4 | Sonda `servidor` |
| Duración de las sesiones con L4×4 | 600 s y 877 s | Marcas de tiempo del log |
| Cuota gastada | 0,87 h: coincide con duración × 2 para L4 más la sesión con T4 | Cálculo sobre esas duraciones |
| Docker en el notebook | Ausente: el sandbox es `subprocess` | Sonda `docker` |

La orden con que se lanzó el servidor en esas corridas quedó guardada en la sonda: no pasaba `--dtype`,
usaba 0,80 de memoria de GPU y reservaba 8 adaptadores de rango 128. La salida del servidor no se guardó.
Que cayera a tiempos distintos en dos corridas iguales (474 s y 753 s) indica que el fallo llega después
de una carga de duración variable, no al arrancar.

Un dato sin explicar: Kaggle registra 86 883 bytes para el envío 56808559, y el zip enviado mide 3 495.
El archivo guardado no se puede bajar por API; se puede bajar desde la página de envíos.

## Sesiones: listar y cancelar

`scripts/kaggle_sesiones.py` lista las sesiones activas o en cola y cancela una.

```bash
# 1. El dueño abre Edge con un perfil aparte e inicia sesión en Kaggle (una vez por perfil):
msedge --remote-debugging-port=9333 --user-data-dir=<perfil aparte> https://www.kaggle.com/account/login
# 2. Listar: sesiones con su identificador, cuota de GPU y versiones del notebook
uv run --with playwright python -m scripts.kaggle_sesiones listar --usuario <usuario> --notebook <notebook>
# 3. Cancelar, con el token de KAGGLE_API_TOKEN
python -m scripts.kaggle_sesiones cancelar --sesion <identificador> --usuario <usuario> --notebook <notebook>
```

- **Cancelar funciona con el token.** La operación es `CancelKernelSession` y pide el identificador de la
  sesión. Con un identificador que no es de la cuenta responde 403.
- **Listar exige la sesión web del dueño.** Ninguna ruta de la API pública entrega el identificador: ni el
  estado, ni los metadatos, ni el flujo de logs. La página sí (`kernelRunId`).
- **El inicio de sesión no se automatiza.** Google rechaza iniciar sesión en un navegador controlado por
  automatización. Por eso el dueño abre Edge normalmente y el guion se conecta después.

### Lo que se hizo y se leyó el 2026-10-04

- Se canceló la versión 2 de `prueba-a-ajustada`, que esperaba en cola desde las 14:42 UTC. Estado
  posterior: `cancelAcknowledged`; sesiones en cola: 0.
- **Por qué se canceló.** La versión 1 esperó 8 h 20 min en cola (creada 00:56 UTC, ejecutada 09:16 UTC),
  corrió 22,7 s y terminó con error: instaló 0 ruedas desde una ruta fija. La versión 2 tenía la misma
  ruta fija: habría fallado igual tras otra espera.
- **Espera en cola con L4:** 8 h 20 min en la única corrida con ese dato.
- **Cuota de GPU:** 1,89 h usadas de 30; reinicio el 2026-10-10 00:00 UTC.
- **Límites de la cuenta:** 2 sesiones por lotes con GPU y 1 interactiva con GPU a la vez.
- **El notebook ejecutado sí se puede bajar** con la sesión web: cada versión terminada trae una dirección
  firmada (`renderedOutputUrl`) con las salidas celda por celda. La API pública no la entrega.
