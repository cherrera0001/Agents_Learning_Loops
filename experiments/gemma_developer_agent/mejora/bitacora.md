# Bitácora del ciclo de mejora del agente del envío (#103)

Una entrada por vuelta. Cada una dice qué se leyó, qué se predijo antes de correr, qué salió y qué se
decide. Es exploratoria: no reemplaza a la línea base pre-registrada ni a la campaña. Lleva solo agregados:
sin enunciados, parches, pruebas ni identificadores de tareas.

## Reglas del ciclo

1. Un cambio por corrida.
2. La predicción se escribe antes de conocer el resultado.
3. Un cambio se conserva solo si mejora más que las tareas que cambian entre dos corridas iguales.
4. Lo que no necesita el modelo se comprueba sin GPU antes de subir: `scripts/kaggle_preflight.py`,
   `scripts/kaggle_simulacro.py` y un ensayo local de las celdas nuevas.
5. El conjunto de desarrollo son 15 tareas de rich que discriminan en el sandbox del notebook de la
   competencia. Las de fastapi no se usan para mejorar nada: son las del repositorio que el pre-registro
   prefiere como prueba.

## Límites del ciclo

| Límite | Valor | Fuente |
|---|---|---|
| Espera en cola de GPU | 8 h 20 min en la única corrida con ese dato | [`docs/rescate_kaggle.md`](../docs/rescate_kaggle.md) |
| Sesiones de GPU por lotes a la vez | 2 | Ídem |
| Envíos al concurso | 1 por día | Reglas de la competencia |
| Cuota de GPU | 30 h semanales; L4×4 cuenta al doble | Comentario en #101 |

Una vuelta con el modelo tarda del orden de medio día.

## Punto de partida (2026-10-04)

| Medida | Valor | Fuente |
|---|---|---|
| Nota pública del envío actual | 0,06, que son 4 de 58 tareas | [`submissions/registry.json`](../submissions/registry.json) |
| Media de un primer envío en la tabla | 3,83 tareas (413 equipos) | [`docs/rescate_kaggle.md`](../docs/rescate_kaggle.md) |
| Mediana de la tabla | 5 tareas | Ídem |
| Tareas públicas que discriminan en el sandbox del notebook | 71 de 129 (rich 42 de 48, fastapi 29 de 67) | [`calibracion/validez_notebook_2026-10-04.json`](../calibracion/validez_notebook_2026-10-04.json) |
| Configuración enviada | Razonamiento desactivado, 4 min, 40 llamadas y 60 s por comando | Pre-registro de la línea base, Enmiendas 2 y 3 |

## Vuelta 1 — 2026-10-04

**Estado leído (19:07 UTC).** Un envío con nota (0,06) y su repetición pendiente. Dos sesiones de GPU en
cola: la prueba de dos tareas y una sesión con varias pasadas. Cuota de GPU usada: 1,89 h de 30.

**Qué se preparó.** Un notebook con tres corridas en una sola sesión de GPU sobre las 15 tareas de
desarrollo, en este orden: configuración enviada, variante con razonamiento, configuración enviada otra vez.
El modelo se carga una vez. No se versiona: lleva celdas del notebook oficial de la competencia.

**Comprobado sin GPU.**

| Comprobación | Resultado |
|---|---|
| `scripts/kaggle_preflight.py` | Pasa |
| Guardia contra la estructura real de `/kaggle/input`, en sus dos disposiciones | Pasa |
| Captura del error del servidor, con el arranque real del arnés y un proceso falso | La causa queda guardada en los dos tipos de fallo |
| Ensayo local de las celdas nuevas con el modelo falso de `scripts/kaggle_simulacro.py` | Flujo, archivo de resultados y limpieza correctos |
| Parámetros que recibe el modelo en cada corrida | Razonamiento desactivado, activado con presupuesto 4 096 y desactivado |

**Qué no se pudo hacer.** Subirlo: la cuenta ya tenía sus dos sesiones de GPU por lotes en cola.

**Predicciones para la primera sesión con el modelo**, escritas antes de cualquier resultado:

| Predicción | La refuta |
|---|---|
| P1. Entre dos corridas iguales cambian de resultado entre 1 y 3 de 15 tareas | 0 tareas, o más de 3 |
| P2. La clase más frecuente entre las no resueltas es el tiempo agotado, con o sin parche | Que la clase más frecuente sea otra |
| P3. Con razonamiento, la diferencia frente a la configuración enviada no supera las tareas que cambian en P1 | Una diferencia mayor |

**Hipótesis para la vuelta siguiente, sin probar.** El arnés toma como parche los cambios que quedan en el
árbol de trabajo aunque la sesión termine sin entregar (comprobado con el modo `sin_submit` del simulacro).
Si la clase dominante resulta ser «tiempo agotado sin parche», el cambio a probar es de instrucciones:
editar primero y verificar después. Si es «el parche no pasa», ese cambio no sirve.

**Decisión.** Esperar a que una sesión con el modelo termine. No se elige ningún cambio antes de tener la
tabla de fallos.
