# Gemma Developer Agent · Agents Learning Loops (ALL)

Espacio de estudio, prototipado y redacción para la participación en los desafíos de Google en Kaggle:

1. **Paper Track:**
   [`gemma-4-developer-agent-paper`](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)
   · *Cierre: 12 de noviembre de 2026*
2. **Code Track:**
   [`gemma-4-developer-agent`](https://www.kaggle.com/competitions/gemma-4-developer-agent)
   · *Cierre: 2 de diciembre de 2026*

---

## 1. Pregunta y Tesis de Investigación

* **Pregunta:** ¿Puede una memoria episódica en grafo asociativo mejorar la selección de contexto en un
  agente de ingeniería de software basado en Gemma 4 sin inducir transferencia negativa ante tareas no
  análogas?
* **Tesis a evaluar:** La hipótesis de ALL es que un grafo asociativo permite seleccionar lecciones
  pertinentes con mayor precisión que un historial textual plano. En el Experimento 1 (Task Ledger, 6 tareas
  originales de software), la memoria asociativa expuso 18/18 lecciones relevantes frente a 18/54 del
  historial plano. Sin embargo, en las tareas con señuelo de H4 esa misma selectividad expuso
  sistemáticamente la lección del señuelo (18/18 expuestas correspondieron al señuelo; ver
  [`docs/results/h4-associative-vs-history.md`](../../docs/results/h4-associative-vs-history.md)), induciendo
  a error al agente. Por tanto, este estudio no asume una ventaja general, sino que evalúa si anclajes
  estructurales más profundos (grafos AST, vecinos de símbolos provistos por `swegemma`) logran discriminar
  la relevancia sin repetir la transferencia negativa medida en H4.

---

## 2. Fronteras y Gobernanza del Repositorio

En estricto cumplimiento de [`AGENTS.md`](../../AGENTS.md),
[`docs/entorno/glosario.md`](../../docs/entorno/glosario.md) y
[`docs/entorno/harness.md`](../../docs/entorno/harness.md):

* **Aislamiento del Experimento 1:** Este estudio no modifica el **solver acotado**
  (`src/experiments/agent.py`) ni el software bajo prueba Task Ledger
  ([`experiments/software_project/`](../software_project/)). Esos componentes permanecen como líneas base
  deterministas cerradas.
* **Inmutabilidad de la evidencia:** Los recibos de `evidence/` y los resultados consolidados de `results/`
  son históricos e intocables. Los datos generados por Kaggle o Gemma se mantienen separados.
* **Seguridad y tokens:** Ningún token de Kaggle (`KGAT...`) ni credencial se versiona en git. Las claves se
  manejan exclusivamente a través de variables de entorno y archivos ignorados (`.env`).
* **Datos pesados fuera de git:** Las subcarpetas `data/`, `artifacts/` y `checkpoints/` están excluidas en
  [`.gitignore`](../../.gitignore).

---

## 3. Estructura del Directorio

```text
experiments/gemma_developer_agent/
├── README.md               # Contexto, tesis y fronteras del estudio
├── conditions/             # Variantes experimentales controladas
│   └── a_kit/              # Condición A: copia íntegra del starter kit oficial (sample_submission/)
│       ├── agent.yaml      # Declaración de LlmAgent base
│       ├── eval_config.yaml# Presupuestos por tarea
│       ├── configs/        # Parámetros de sampling
│       ├── prompts/        # Prompts de sistema y analizador
│       ├── sub_agents/     # Definición declarativa de code_analyzer_agent
│       └── adapters/       # Configuraciones y manifiesto SHA-256 de adaptadores LoRA (pesos ignorados)
├── drafts/                 # Borradores exploratorios sin condición asignada
│   ├── README.md           # Explicación del estado de los borradores
│   ├── agent.yaml          # Borrador de agente exploratorio
│   ├── preregistration_abcd.md # Borrador preliminar de diseño experimental
│   ├── paper/              # Borrador preliminar de manuscrito
│   ├── skills/             # Borradores de directivas escritas a mano
│   └── architecture_explainer.html # Diagrama de intención conceptual
├── docs/                   # Especificaciones oficiales verificadas e historial de supervisión
│   ├── kaggle_specifications.md         # Ficha técnica verificada contra HARNESS_README.md
│   ├── supervision-claude-2026-10-02.md    # Supervisión v1 del orquestador Claude
│   ├── supervision-claude-2026-10-02-v2.md # Supervisión v2 del orquestador Claude
│   └── supervision-claude-2026-10-02-v3.md # Supervisión v3 del orquestador Claude
├── data/                   # (Ignorado por git) Datasets y starter kit descargados vía API
├── artifacts/              # (Ignorado por git) Entregables intermedios, figuras y PDFs
└── checkpoints/            # (Ignorado por git) Pesos o estados locales
```

---

## 4. Fases y Estado

- [x] **Fase 0 · Entorno y API:** Conexión con la API de Kaggle verificada y token seguro en `.env` (ignorado
  por git).
- [x] **Fase 1 · Especificaciones Técnicas y Condición A:** Especificaciones verificadas contra
  `data/HARNESS_README.md` (`docs/kaggle_specifications.md`) y réplica exacta de `sample_submission/` en
  `conditions/a_kit/`.
- [x] **Fase 2 · Limpieza y Aislamiento de Borradores:** Retiro de código Python fuera del contrato de
  submission (`gemma_agent.py`, `estimation.py`), resolución de colisiones de paquetes
  (`experiments/__init__.py`) y traslado de borradores no consolidados a `drafts/`.
- [ ] **Fase 3 · Definición y Pre-registro Experimental (#103):** Formulación del protocolo A/B/C/D, split
  estratificado de tareas públicas y pre-registro formal antes de cualquier cómputo.
- [ ] **Fase 4 · Ejecución Experimental y Redacción (#104-#106):** Minería offline, consolidación verificada y
  preparación de entregables para Code Track y Paper Track.
