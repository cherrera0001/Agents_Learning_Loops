# AGENTS.md

Instrucciones para cualquier **agente de entorno**: una persona o un agente de Cursor o Claude que edita
este repositorio. El contrato completo está en [`docs/entorno/`](docs/entorno/README.md).

1. **Lee el [glosario](docs/entorno/glosario.md).** «Agente», «skill» y «harness» tienen dos o tres
   significados distintos en este repositorio. Usa siempre el nombre exacto: agente de biblioteca, solver
   acotado, agente de entorno, skill de memoria, skill de entorno, harness de experimento, harness de
   entorno.
2. **Antes de delegar o de implementar, lee [`docs/estimation.md`](docs/estimation.md)**: estima la talla y
   usa el ID y el esfuerzo de esa fila. Este archivo no cambia el modelo de tu sesión; el ID se aplica al
   crear el subagente o el worktree ([`docs/entorno/enrutamiento.md`](docs/entorno/enrutamiento.md)).
3. **Ejecuta el ciclo de la bitácora** ([`learning/README.md`](learning/README.md)):
   - antes de implementar, [`recall-antes-de-issue`](skills/recall-antes-de-issue/SKILL.md);
   - al terminar, [`registrar-episodio`](skills/registrar-episodio/SKILL.md) y `python -m scripts.devlog rebuild`.
4. **Respeta la frontera de fuga.** El solver acotado nunca recibe `benchmark/private/`, causas ocultas,
   parches dorados ni el checkout completo. Solo el evaluador del experimento lee `benchmark/private/`.
5. **No reescribas evidencia.** Los recibos de `evidence/` y los agregados de `results/` no se editan a
   mano: se corrige el código y se publica una campaña nueva identificada
   ([`proteger-evidencia`](skills/proteger-evidencia/SKILL.md)).
6. **Detente** cuando pasen los tests y las comprobaciones de [`CONTRIBUTING.md`](CONTRIBUTING.md). El
   implementador abre un PR con `Closes #<n>` y no hace merge; el merge lo hace el orquestador después de
   verificar `mergedAt`.

Roles: [`docs/entorno/agentes.md`](docs/entorno/agentes.md) · Permisos, parada y evidencia:
[`docs/entorno/harness.md`](docs/entorno/harness.md).
