"""Fase 3: calibracion de las predicciones selladas.

Comprueba:
1. Sello intacto: git log/diff sobre analisis_c7/predicciones.csv (no modificada tras el sellado).
2. Estado del objetivo sub-019: envios.csv/registry -> score real conocido? (calibracion evaluable?)
3. Bases internas de cada prediccion vs datos recomputados.
Salida: salida_08_predicciones.txt
"""
import csv
import json
import subprocess

AN = "experiments/gemma_developer_agent/analisis_c7"
BASE = "experiments/gemma_developer_agent"


def git(args):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=".")
    return r.stdout.strip()


def main():
    out = []
    out.append("== 1. Sello ==")
    out.append(git(["log", "--oneline", "--follow", "--", f"{AN}/predicciones.csv"]))
    out.append("diff working tree vs HEAD: " + (git(["diff", "--stat", "HEAD", "--", f"{AN}/predicciones.csv"]) or "(sin cambios)"))
    out.append("status: " + (git(["status", "--porcelain", f"{AN}/predicciones.csv"]) or "(limpio)"))

    preds = list(csv.DictReader(open(f"{AN}/predicciones.csv", encoding="utf-8")))
    envios = list(csv.DictReader(open(f"{AN}/envios.csv", encoding="utf-8")))
    sub19 = [e for e in envios if e["submission_id"] == "sub-019"][0]
    out.append("")
    out.append("== 2. Calibracion sub-019 ==")
    out.append(
        f"prediccion sellada: {sub19 and ''}score={preds[0]['prediccion']} IC [{preds[0]['intervalo_inf']},{preds[0]['intervalo_sup']}] sellado {preds[0]['timestamp_sellado_utc']}"
    )
    out.append(
        f"estado real en envios.csv: status={sub19['status']} public_score={sub19['public_score'] or 'VACIO'}"
    )
    reg = json.load(open(f"{BASE}/submissions/registry.json", encoding="utf-8"))
    txt = json.dumps(reg, ensure_ascii=False)
    import re
    m = re.search(r'"submission_id":\s*"sub-019".*?"public_score":\s*([^,"]*)', txt)
    out.append(f"registry.json sub-019 public_score: {m.group(1) if m else 'no encontrado'}")
    sc19 = [p for p in preds if p["objetivo"] == "sub-019_LB_score"][0]
    real = sub19["public_score"]
    out.append(
        f"VEREDICTO CALIBRACION: {'NO EVALUABLE AUN (score no conocido; sub-019 PENDING t+' + 'horas)' if not real else 'evaluable'}"
    )
    out.append(f"  (si cayera hoy: dentro de ruido si |real-0.10|<=0.041; senal si >0.14; contrasenal si <0.06)")

    out.append("")
    out.append("== 3. Bases internas vs recomputado ==")
    filas = list(csv.DictReader(open(f"{AN}/corridas_tareas.csv", encoding="utf-8")))
    b = lambda v: str(v).strip().lower() in ("true", "1")
    r1 = [f for f in filas if f["fuente"].startswith("replica1")]
    it = [f for f in filas if f["fuente"].startswith("iteracion")]
    n_r1 = sum(b(f["resuelta"]) for f in r1)
    n_it = sum(b(f["resuelta"]) for f in it)
    for p in preds:
        if p["objetivo"] == "sub-019_LB_score":
            continue
        out.append(f"  {p['objetivo']}: pred {p['prediccion']} IC [{p['intervalo_inf']},{p['intervalo_sup']}] base={p['base'][:70]}")
    out.append(f"  [recomputado] lunes_A: replica1 = {n_r1}/20 (prediccion 4/20 [2,6])")
    out.append(f"  [recomputado] lunes_thinking base '17-18%': iteraciones = {n_it}/{len(it)} = {n_it/len(it)*100:.1f}% (~17%)")
    muro_muertes = sum(b(f["muro"]) and not b(f["resuelta"]) for f in r1)
    out.append(
        f"  [recomputado] lunes_presupuesto base '75% muertes en muro': {muro_muertes}/20 = {muro_muertes/20*100:.0f}% (el 75% del doc esta corregido a {muro_muertes}/20; ver salida_03)"
    )
    open("scratch/concilio-c7-fase4/analista-datos/salida_08_predicciones.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
