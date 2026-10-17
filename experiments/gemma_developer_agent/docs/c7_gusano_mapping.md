# Del gusano autónomo al quinto brazo: extracción y mapeo al arnés swegemma

Extracción **offline** (sin GPU) de `reports/Investigación en gusanos autónomos.md` (resumen de
investigación del dueño, 2026-10-13) con el análogo en el arnés `swegemma` por cada principio.
Alimenta el diseño del quinto brazo experimental «forrajeo» (`replicas_c7_forrajeo/`, WIP) para el
contraste del lunes. Rama `exp/kaggle-c7-replicates`. Todo lo de este documento es literatura +
código ya commiteado: ningún dato nuevo de competición.

## Trazabilidad

- Fuente biológica: `reports/Investigación en gusanos autónomos.md` (sección citada en cada
  bloque; los enlaces DOI viven en ese documento, no se repiten aquí).
- Fuente del arnés: `data/HARNESS_README.md` (ignorado por git; sección citada en cada análogo).
- Disciplina: el brazo forrajeo cambia **solo** `prompts/system.md` (§2.2 del HARNESS_README), igual
  que los brazos navegación, presupuesto y thinking; el lazo multi-turno, las herramientas y los
  presupuestos quedan fijos (§5.3, §6, §7.1).

## (a) Los cuatro niveles de autonomía

Del documento (sección «Los robots ejecutan marchas ya escritas» y Conclusión), cuatro logros que
«aún no coinciden en un objeto», del más débil al más fuerte:

1. **Marcha escrita en un banco externo**: una secuencia gobierna actuadores sin sensado de
   entorno (Das 2023: electroválvulas + placa; sin sensores en la locomoción).
2. **Oscilador físico sin cómputo**: un anillo de puertas neumáticas sostiene la onda mientras
   haya presión (Das 2026, 2 bar; dirección elegida al cablear).
3. **Cómputo y energía a bordo con la secuencia ya escrita**: Meshworm (ATmega88PA + batería,
   3 mm/s) avanza sin ordenador externo, pero la marcha está programada.
4. **La acción cambia porque un sensor a bordo lo decide**: el robot de *Science Robotics* invierte
   la onda ante un choque medido (33,6 % vs 28,6 % de «pandeo»); ningún sistema abierto aprende
   de sus pruebas dentro del cuerpo.

Sobre estos cuatro, el documento coloca el sentido fuerte organizacional (Bechtel & Bich 2023: el
organismo se mantiene lejos del equilibrio por su propia actividad), que solo el animal vivo
cumple.

**Análogo en el arnés**: el agente swegemma es de nivel 4 **por construcción** — las observaciones
de herramienta regresan al bucle `while True:` del corredor y condicionan la siguiente acción
(§5.3) — y nuestros cinco brazos mantienen ese nivel fijo variando solo la política en texto
(`system.md`, §2.2): el contraste del lunes mide políticas de nivel 4, no niveles de autonomía.

## (b) La paradoja del lazo cerrado de BAAIWorm

Del documento (sección «OpenWorm empuja el cuerpo y BAAIWorm cierra un zigzag», Zhao et al. 2024):
BAAIWorm (136 de 302 neuronas, lectura lineal de motoneuronas, 30 fps) produce con señal periódica
**sin** retroalimentación una trayectoria en Z «extremadamente similar» al experimento; al cerrar
el lazo (la corriente sensorial depende de la posición del cuerpo), la trayectoria queda **menos
regular que la experimental** — el acople alejó la película del laboratorio en el mismo artículo
que anunciaba el cierre. El documento lo resume: «BAAIWorm invierte la expectativa de que añadir
biología acerca el modelo al dato».

**Análogo en el arnés**: añadir un mecanismo a un agente puede alejarlo de su línea base medida —
justificación del protocolo *measure-before-submit* de esta campaña: réplica offline + banda de
ruido antes de gastar el presupuesto de evaluación de 12 h, y cada variante se compara contra el
brazo A en las mismas 20 tareas, no contra la intuición de que «más mecanismo = mejor».

## (c) Pirueta/sesgo y la secuencia local→global con sus constantes de tiempo

Del documento (sección «El nematodo ya alterna estados, taxis y memoria», Haley & Chalasani 2024;
Flavell, Raizen y You): el taxis químico se explica con dos componentes — las **piruetas** se
hacen más frecuentes al bajar un atrayente y la ondulación se **sesga** hacia él — y ambos bastan
para la conducta observada; la decisión de reorientar está en la red (AVA correlaciona con el
inicio y fin del reverso; el sensor AWC no predice el instante). Fuera de la comida la secuencia es
fija: **~15 minutos de búsqueda local** con muchos giros de ángulo alto y **después búsqueda
global**. Sobre comida, el animal es biestable: roaming ~0,1 mm/s (20 % del tiempo, tandas de 1-2
min) frente a dwelling <0,05 mm/s (80 %, tandas de 5-10 min; OP50).

**Análogo en el arnés**: la búsqueda del sitio de edición reproduce esa arquitectura con las
herramientas de grafo (§6.3): búsqueda local = extraer identificadores → `search_similar_code` →
`get_code_neighbors` → leer; escalada global = ensanchar la consulta y cambiar de estrategia
cuando la local no rinde. El brazo forrajeo fija la escalada a las constantes del presupuesto
(`get_status()` es gratuita, §6.1): fracción del tope de 4,5 min por tarea en lugar de los 15 min
del gusano, con roaming/dwelling mapeados a explorar/leer-con-cuidado.

## (d) Habituación y entrenamiento espaciado

Del documento (sección «El nematodo…», Rankin 1990; Ardiel & Rankin 2010; Rose & Rankin 2001):
los golpes repetidos reducen amplitud y frecuencia del retroceso, y un choque eléctrico breve
devuelve la respuesta — habituación, distinta de fatiga y de adaptación sensorial. Los intervalos
cortos habitúan más rápido, más hondo y con recuperación más rápida. La memoria a 24 h **exige
cuatro bloques separados por una hora** (20 golpes a intervalo de 60 s); ochenta golpes masivos, o
el mismo número a intervalo de 10 s, **no** la dejan. La retención depende de síntesis de
proteínas y del receptor AMPA GLR-1 (necesario para retener, no para habituar).

**Análogo en el arnés**: la memoria de fallos del bucle de aprendizaje del repo — una lección
consolidada de un episodio y rehearsed en sesiones espaciadas baja la tasa de repetición, mientras
la repetición masiva dentro de una sesión no deja memoria utilizable; dentro de una tarea, la
política debe cambiar tras dos fallos idénticos de la misma acción (habituación operativa) en
lugar de reintentar el mismo movimiento.

## (e) «La conectividad sola no basta»

Del documento (secciones «El cableado no lee ese repertorio» y «…zigzag»; Izquierdo & Beer 2016;
Cook et al. 2019; Kramer & Flavell 2024): la conducta es producto del sistema nervioso **y** de la
retroalimentación continua de la biomecánica y el entorno — la conectividad sola es insuficiente
porque el conectoma no anota el signo sináptico ni la neuromodulación; la anatomía no predice la
actividad; el conectoma peptidérgico es más de diez veces más denso que el sináptico y une la
faringe al cerebro central; monoaminas y péptidos «fijan la agenda mientras la transmisión
ionotrópica la ejecuta» (Bechtel & Bich 2023).

**Análogo en el arnés**: el resultado negativo de calibración offline (preregistrado,
`docs/results/offline-calibration.md`) — α y η_h inertes bajo el embedder léxico, solo τ_seed
movió, y las ventanas en desacuerdo — es la misma forma en nuestro dominio: el grafo de memoria
conectado y completo no basta; los «neuromoduladores» (parámetros de recuperación) no produjeron
mejora conductual medible. **Framing analógico, no evidencia biológica**: lo reportamos como
paralelo estructural, no como confirmación de la tesis en gusanos.

## Lectura

Los cinco principios entran en el brazo forrajeo como política de búsqueda con escalada
temporalizada, decisión de reorientación tras estancamiento, modos explotar/explorar y cambio de
acción tras fallo repetido — cada uno etiquetado con su fuente biológica en
`replicas_c7_forrajeo/kit_forrajeo/prompts/system.md`. La decisión de reorientar «está en la red,
no en el sensor» tiene su paralelo deliberado: la política vive en `system.md` (texto declarativo,
§2.1), no en código del arnés. Límite: el mapeo es por analogía de diseño; ningún número de este
documento pretende validez más allá del contraste del lunes.
