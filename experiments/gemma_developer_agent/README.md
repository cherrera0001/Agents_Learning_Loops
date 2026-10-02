# Gemma Developer Agent · Agents Learning Loops (ALL)

Espacio de estudio, prototipado y redacción para la participación en los desafíos de Google en Kaggle:

1. **Paper Track:** [`gemma-4-developer-agent-paper`](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper) · *Cierre: 12 de noviembre de 2026*
2. **Code Track:** [`gemma-4-developer-agent`](https://www.kaggle.com/competitions/gemma-4-developer-agent) · *Cierre: 2 de diciembre de 2026*

---

## 1. Pregunta y Tesis de Investigación

* **Pregunta:** ¿Cómo condiciona una memoria episódica en grafo asociativo las decisiones de un agente de ingeniería de software basado en Gemma 4, sin saturar su ventana de contexto y preservando la frontera frente a la transferencia negativa?
* **Tesis (ALL):** Los agentes autónomos sin memoria (*stateless*) repiten fallos ante tareas análogas, mientras que los historiales planos de texto saturan la ventana de inferencia con lecciones no pertinentes. El marco **Agents Learning Loops (ALL)** introduce una memoria asociativa con activación propagada (Collins & Loftus) que expone lecciones quirúrgicas (18/18 relevantes frente a 18/54 en historial plano en el experimento sintético).
* **Rigor y Límites:** El estudio incorpora los resultados negativos del marco (**H4**): ante señuelos léxicos o trampas de coincidencia superficial entre tareas de un mismo proyecto de software (Task Ledger), la memoria puramente léxica indujo a error (transferencia negativa). El objetivo científico es caracterizar esta frontera y evaluar si anclajes semánticos y topológicos más profundos (AST, vecinos de símbolos, grafos de código provistos por el arnés oficial) mitigan este fenómeno.

---

## 2. Fronteras y Gobernanza del Repositorio

En estricto cumplimiento de [`AGENTS.md`](../../AGENTS.md), [`docs/entorno/glosario.md`](../../docs/entorno/glosario.md) y [`docs/entorno/harness.md`](../../docs/entorno/harness.md):

* **Aislamiento del Experimento 1:** Este estudio no modifica el **solver acotado** (`src/experiments/agent.py`) ni el software bajo prueba Task Ledger ([`experiments/software_project/`](../software_project/)). Esos componentes permanecen como líneas base deterministas cerradas.
* **Inmutabilidad de la evidencia:** Los recibos de `evidence/` y los resultados consolidados de `results/` son históricos e intocables. Los datos generados por Kaggle o Gemma se mantienen separados.
* **Seguridad y tokens:** Ningún token de Kaggle (`KGAT...`) ni credencial se versiona en git. Las claves se manejan exclusivamente a través de variables de entorno y archivos ignorados (`.env`).
* **Datos pesados fuera de git:** Las subcarpetas `data/`, `artifacts/` y `checkpoints/` están excluidas en [`.gitignore`](../../.gitignore).

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
│   └── skills/             # Borradores de skills escritas a mano
│       └── all_core/
│           └── SKILL.md
├── docs/                   # Especificaciones oficiales verificadas e historial de supervisión
│   ├── architecture_explainer.html      # Diagramas conceptuales de ALL
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

- [x] **Fase 0 · Entorno y API:** Conexión con la API de Kaggle verificada y token seguro en `.env` (ignorado por git).
- [x] **Fase 1 · Especificaciones Técnicas y Condición A:** Especificaciones verificadas contra `data/HARNESS_README.md` (`docs/kaggle_specifications.md`) y réplica exacta de `sample_submission/` en `conditions/a_kit/`.
- [x] **Fase 2 · Limpieza y Aislamiento de Borradores:** Retiro de código Python fuera del contrato de submission (`gemma_agent.py`, `estimation.py`), resolución de colisiones de paquetes (`experiments/__init__.py`) y traslado de borradores no consolidados a `drafts/`.
- [ ] **Fase 3 · Definición y Pre-registro Experimental (#103):** Formulación del protocolo A/B/C/D, split estratificado de tareas públicas y pre-registro formal antes de cualquier cómputo.
- [ ] **Fase 4 · Ejecución Experimental y Redacción (#104-#106):** Minería offline, consolidación verificada y preparación de entregables para Code Track y Paper Track.
