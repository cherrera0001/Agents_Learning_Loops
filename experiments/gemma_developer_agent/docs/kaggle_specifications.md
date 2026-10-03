# Kaggle Gemma 4 Developer Agent: ficha de reglas y datos del concurso

Ficha de referencia de las reglas del concurso, tomada de las páginas públicas de las dos pistas y de la
respuesta de la API de Kaggle ([`kaggle_api_2026-10-02.json`](kaggle_api_2026-10-02.json), registro del
2026-10-02). **Manda la página oficial**: esta ficha puede quedar desactualizada. Cada dato cita la página
y, cuando existe, la sección. Las páginas se leyeron el 2026-10-02 en copias locales (`data/pages/`), que git
ignora y que un lector no puede abrir desde este repositorio; para comprobar una cita hay que ir a la
página de la competencia ([Code Track](https://www.kaggle.com/competitions/gemma-4-developer-agent),
[Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)). No se consultaron las
páginas vivas ni el foro.

El arnés de la competencia se cita por sección («HARNESS § X.Y») y con palabras propias, sin reproducir su
texto, por la regla de no redistribución de los datos (Rules § 2.4.b, antes citada aquí como «Sección 4»).
El `HARNESS_README` es un archivo local que no se versiona.

---

## 1. Fechas y metadatos

| Parámetro | Code Track (`id: 149921`) | Paper Track (`id: 163111`) | Fuente |
|---|---|---|---|
| Cierre de envíos | 2026-12-02 23:59 UTC | 2026-11-12 23:59 UTC | `Timeline` de cada pista |
| Límite de envíos | 1 al día; 2 envíos finales | 5 al día | Rules § 2.2 |
| Fusión de equipos | 2026-11-25 23:59 UTC | 2026-11-12 23:59 UTC | Code: `Timeline`. Paper: solo la API (`mergerDeadline`); su `Timeline` no la trae |
| Tamaño de equipo | Hasta 5 personas | Hasta 5 personas | Rules § 2.1 |
| Premios | 65 000 USD en total: 37 000, 18 000 y 10 000 | 35 000 USD, tres premios | Página `Prizes`; los 100 000 USD son la suma de las dos pistas |
| Entrada | Aceptar las reglas antes del 2026-11-25 | Inscripción independiente | `Timeline` y reglas de cada pista |

La instantánea de la API es del 2026-10-02 y dice que la cuenta no había entrado en la pista de artículo
(`userHasEntered: false`). El 2026-10-03 la API confirmó la inscripción en las dos pistas (comentario del
issue #101).

---

## 2. Code Track: entorno de evaluación y restricciones

### 2.1 Cómputo

- **Máquina de evaluación:** 4 × NVIDIA L4 (96 GB de VRAM en total), con el servidor de modelos descrito en
  HARNESS § 3.1.
- **Notebooks de Kaggle:** los que usan aceleradores L4×4 consumen la cuota semanal de GPU al doble del ritmo
  estándar (página `Upgraded Accelerators`, que habla de notebooks, no de la máquina de evaluación). La
  página avisa de que ese factor puede subir.
- **Cuota de la cuenta:** 30,00 h semanales de GPU, con reinicio el 2026-10-10 a las 00:00 UTC, leída por la
  API de Kaggle el 2026-10-03 (comentario del issue #101). No está versionada, y no se ha confirmado que la
  cuenta pueda elegir L4×4.

### 2.2 Presupuesto y tiempo

- **Límite global:** 12 horas para entregar parches de todas las tareas, con el montaje del contenedor
  incluido y sin contar la validación de los parches (página `Evaluation`).
- **Presupuesto por tarea:** opcional, en el archivo declarativo `eval_config.yaml` del envío (página
  `Evaluation`; opciones en HARNESS § 7.1). Los valores por defecto del guion de puntuación son 60 minutos,
  100 llamadas a herramientas, 500 turnos y 300 s por comando, y son configurables; la regla del concurso es
  el límite global de 12 horas.
- **Contexto del modelo:** 32 768 tokens; el guion de puntuación compacta el contexto a partir de unos 14 000
  (HARNESS § 3.1 y § 7.2).

### 2.3 Conjunto de prueba

- **Composición:** unas 120 tareas, repartidas por mitades entre las tablas pública y privada (página
  `Data`). La tabla privada decide el resultado (Foundational § 7.a).
- **Origen:** el conjunto de prueba se curó a partir de repositorios privados (página `Data`). Las 129 tareas
  del paquete público (fastapi, rich, requests y httpx) son tareas de entrenamiento publicadas (HARNESS
  § 9.1) y no corresponden a los repositorios con que se puntúa.

### 2.4 Modelo, adaptadores y contenido del envío

- **Modelo:** solo la variante
  [`gemma-4-31b-it-qat-w4a16-ct`](https://www.kaggle.com/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct)
  en todos los agentes y subagentes (página `Model Selection, Budget, and Harness Rules`; HARNESS § 3.2). Es
  un dato del reglamento, no una verificación de Google sobre esa variante.
- **Adaptadores LoRA:** formato `.safetensors`, distintos por agente, hasta 8 y de rango máximo 128 (HARNESS
  § 3.3 y § 3.4).
- **Contenido del envío:** solo declarativo, sin punto de entrada en Python. Las skills son carpetas con
  `SKILL.md`, `scripts/` y `resources/` (HARNESS § 2.1; página `Evaluation`).
- **Límites del envío:** menos de 3 GiB, 10 000 archivos, 1 000 skills y 50 MiB por skill (HARNESS § 2.4).
- **Herramientas:** las nueve del arnés y los subagentes propios; los guiones de las skills gastan del
  presupuesto (página `Model Selection, Budget, and Harness Rules`; HARNESS § 6).
- **Aislamiento:** un contenedor de agente por tarea, sin red; el espacio de trabajo se borra al reutilizarlo
  (HARNESS § 4.1 y § 5.1). Ninguna página describe un canal de memoria entre tareas.

### 2.5 Datos y licencias

- **Uso de los datos:** para cualquier fin, también académico y comercial (Rules § 2.4.a).
- **Publicación:** está prohibido publicar, duplicar o pasar los datos a quien no participa; «datos» incluye
  el código que da el sitio (Rules § 2.4.b; Foundational § 18.a).
- **Código en público:** la regla pide hacerlo en el foro o en los notebooks de la competencia, bajo licencia
  abierta (Foundational § 5.d y § 6.a–b). Un repositorio de GitHub por sí solo no lo cumple al pie de la
  letra, y las páginas no dicen si agregados o identificadores de tarea son «datos».
- **Ganadores:** licencian el envío y el código que lo generó bajo licencia abierta y entregan una
  descripción reproducible (Rules § 1.6, § 2.5 y § 2.8).
- **Datos y modelos externos:** permitidos si son públicos y de costo razonable para todos (Rules § 2.6).

---

## 3. Paper Track: reglas, formato y criterios (ID 163111)

### 3.1 Formato de entrega

- **Modalidad:** Kaggle Writeup de hasta 3 000 palabras, original y no publicado; hay que pulsar «Submit»
  (página `Submission Requirements`).
- **Estructura:** título y subtítulo, resumen, introducción, métodos y experimentos, y trabajo relacionado
  con citas, que es obligatorio (página `Submission Requirements`).
- **Independencia:** no se exige haber participado en el Code Track (página `Description`).

### 3.2 Criterios del jurado

Cinco criterios de igual peso, de 0 a 5 puntos cada uno (página `Evaluation` del Paper Track). Lo que sigue
resume lo que la página pregunta por cada criterio y no añade nada:

| Criterio | Qué pregunta la página |
|---|---|
| Novelty | Si aporta ideas nuevas, profundiza la comprensión o destaca propiedades de métodos existentes |
| Quality | Qué tan general es el enfoque fuera de la competencia |
| Relevance | Qué impacto tiene en ingeniería de software y en el aprendizaje de agentes |
| Verifiability | Si se entiende cómo funciona y cómo se obtuvieron, analizaron e interpretaron los datos |
| Clarity | Si está bien presentado y escrito |

---

## 4. Referencias al arnés de evaluación (`swegemma`)

Para el funcionamiento interno del evaluador, las secciones del `HARNESS_README`:

- Estructura del envío (`submission.zip`): HARNESS § 2.2.
- Clases de agente declarativo (`LlmAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent`): HARNESS § 2.3.
- Ciclo de vida en dos contenedores, de agente y de verificación: HARNESS § 4.1 y § 4.2.
- Herramientas de ejecución, archivos y grafo de código: HARNESS § 6.
- Métrica de resolución y validación de pruebas: HARNESS § 8.

---

## 5. Directrices propias de ALL (no son reglas del concurso)

Esta sección **no es del concurso**: son decisiones de diseño del experimento y pueden cambiar. Las reglas
están en las secciones anteriores.

1. **Agnosticismo de repositorio.** Como el conjunto de prueba oculto viene de repositorios privados (`Data`),
   la consolidación de skills debería apoyarse en patrones generales de diagnóstico y no en convenciones de
   un repositorio de entrenamiento.
2. **Presupuesto acotado.** El límite global de 12 horas para unas 120 tareas deja como mucho 5,4 minutos de
   reloj por tarea de agente y montaje, con una reserva del 10 %, y el pre-registro de la línea base A
   calcula entre 3 y 5 minutos por tarea con concurrencia 1
   ([pre-registro](../../../docs/preregistration/kaggle-baseline-a.md), sección D.1;
   `python -m scripts.kaggle_prereg presupuesto`). Dividir 720 minutos entre 120 tareas, sin reserva ni
   montaje, da 6 minutos y no es una cota válida.
3. **Ciencia abierta.** Los artefactos del experimento deben poder reproducirse desde código versionado y
   manifiestos con SHA-256, sin redistribuir datos del concurso.
