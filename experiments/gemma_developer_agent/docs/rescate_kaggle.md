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
