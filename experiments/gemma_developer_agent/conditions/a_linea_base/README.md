# Envío de la línea base A

Directorio del envío con que se corre la condición A en el experimento de #103
([pre-registro](../../../../docs/preregistration/kaggle-baseline-a.md), sección D). Es el kit oficial con
un solo archivo cambiado: `eval_config.yaml`.

## Qué se versiona

Solo dos archivos propios: este `README.md` y `eval_config.yaml`. El `eval_config.yaml` todavía no existe:
entra en el commit C5 del pre-registro, cuando el presupuesto esté fijado, con los bytes exactos que
genera `scripts/kaggle_prereg.py` desde la fórmula.

Los demás archivos son copias del kit de la competencia y **no se versionan** (regla 4 de la competencia,
no redistribución). `.gitignore` los excluye y `scripts/verify_no_competition_data.py` da alerta si
aparece versionado aquí cualquier otro archivo, aunque esté modificado.

## Cómo se arma

1. Reconstruir y verificar el kit: `python experiments/gemma_developer_agent/conditions/a_kit/download_kit.py`
   (comprueba cada archivo contra [`manifest.json`](../a_kit/manifest.json)).
2. Copiar a este directorio todos los archivos de `conditions/a_kit/` que figuran en `manifest.json`,
   salvo `eval_config.yaml`. No se copian `README.md`, `manifest.json` ni `download_kit.py` de `a_kit/`.
3. Dejar el `eval_config.yaml` versionado de este directorio.
4. Si el ensayo de notebook obligó a bajar `max_output_tokens` (pre-registro, sección A.0), se cambia ese
   único valor en la copia local del archivo de muestreo. Esa copia tampoco se versiona: queda en el hash
   del envío.
5. `python -m scripts.kaggle_prereg comprobar --tasks <tasks.jsonl> --envio <este directorio>` recalcula el
   hash del envío y lo compara con el declarado.

El `README.md` de este directorio entra en el hash del envío, como cualquier otro archivo, y ningún
archivo del envío lo incluye. Que el compilador del arnés acepte el directorio con este archivo dentro
**no está comprobado**: se comprueba en el piloto (sección D.2), que es la primera corrida con este
directorio; el ensayo de notebook usa el kit original. Si no lo acepta, el README se saca del directorio
antes del primer recibo y se anota como enmienda.
