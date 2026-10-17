"""qa06 — Verificación de cifras concretas del documento c7_analisis_critico.md.

A1: join corridas_tareas × tareas_features (n=168): enunciado 1672 vs 159; patch_lineas 16 vs 30.
A2: primera edición 5 vs 20 (n=103); errores 1.7 vs 2.4.
Q1: tasa submit 91% (135/148) y 20% (4/20); muro 15/20 y '0/148 bajo 230s'; medianas 272 vs 79-93.
"""
import csv
import json
import pathlib
import statistics as st

import trazas_rep1

BASE = pathlib.Path(__file__).resolve().parents[3] / "experiments" / "gemma_developer_agent"
OUT = pathlib.Path(__file__).resolve().parent / "salidas"
OUT.mkdir(exist_ok=True)

filas = list(csv.DictReader(open(BASE / "analisis_c7/corridas_tareas.csv")))
feat = {r["instance_id"]: r for r in csv.DictReader(open(BASE / "analisis_c7/tareas_features.csv"))}

lineas = []
def emite(s=""):
    print(s)
    lineas.append(s)

# --- A1
res_f = [r for r in filas if r["resuelta"] == "True"]
nor_f = [r for r in filas if r["resuelta"] != "True"]
enun = lambda r: float(feat[r["task_id"]]["enunciado_chars"])
pline = lambda r: float(feat[r["task_id"]]["patch_lineas"])
emite(f"A1 join n=168: resueltas {len(res_f)}, no resueltas {len(nor_f)}")
emite(f"  enunciado_chars mediana: resueltas {st.median([enun(r) for r in res_f]):.0f} vs no resueltas {st.median([enun(r) for r in nor_f]):.0f}")
emite(f"  patch_lineas mediana: resueltas {st.median([pline(r) for r in res_f]):.0f} vs no resueltas {st.median([pline(r) for r in nor_f]):.0f}")
n_join = sum(1 for r in filas if r["task_id"] in feat)
emite(f"  filas con tarea en features: {n_join}/168")
pa = [feat[r["task_id"]]["patch_archivos"] for r in filas]
emite(f"  patch_archivos: valores {sorted(set(pa))} (columna constante?)")

# --- A2
it = [r for r in filas if r["fuente"] != "replica1_c7_4.5min"]
con = [r for r in it if r["primera_edicion_llamada"] != ""]
fe_res = [int(r["primera_edicion_llamada"]) for r in con if r["resuelta"] == "True"]
fe_nor = [int(r["primera_edicion_llamada"]) for r in con if r["resuelta"] != "True"]
emite(f"A2 n={len(con)} con primera edición: mediana {st.median(fe_res)} vs {st.median(fe_nor)}")
err_res = [int(r["err_tool_count"]) for r in con if r["resuelta"] == "True"]
err_nor = [int(r["err_tool_count"]) for r in con if r["resuelta"] != "True"]
emite(f"A2 errores medias: {st.mean(err_res):.2f} vs {st.mean(err_nor):.2f}")

# --- Q1 submits
raw = {}
for p in sorted((BASE / "data/rescate_kaggle/2026-10-06T1910Z/notebooks").glob("iteracion-0*/salida__iteracion_0*.json")):
    d = json.load(open(p))
    for corr, c in d["corridas"].items():
        for t in c["tareas"]:
            raw[(corr, t["instance_id"])] = t
sub_era = sum(1 for r in it if raw[(r["corrida"], r["task_id"])]["anatomia"]["herramientas"].get("submit_patch", 0) > 0)
emite(f"Q1 submit era: {sub_era}/148 = {sub_era/148:.1%}")
tr = trazas_rep1.cargar_todas()
sub_rep = sum(1 for t in tr.values() if any(c["nombre"] == "submit_patch" for c in t["llamadas"]))
sub_rep_ok = sum(1 for t in tr.values() if t["submit_ok"])
emite(f"Q1 submit réplica1: {sub_rep}/20 llamaron submit_patch; {sub_rep_ok}/20 ok "
      f"(el doc afirma «tasa de submit 20% (4/20)» — 4/20 es la tasa de RESOLUCIÓN)")

# --- Q1 muro
rep = [r for r in filas if r["fuente"] == "replica1_c7_4.5min"]
muro_rep = sum(1 for r in rep if r["muro"] == "True")
muro_era = sum(1 for r in it if r["muro"] == "1")
emite(f"Q1 muro ≥260s réplica1: {muro_rep}/20 ({muro_rep/20:.0%}); muro ≥230s era: {muro_era}/148 ({muro_era/148:.1%}) "
      f"(doc: «0/148 bajo el umbral de 230 s»)")
seg_rep = [float(r["segundos_reloj"]) for r in rep]
seg_era = [float(r["segundos_reloj"]) for r in it]
emite(f"Q1 medianas: réplica1 {st.median(seg_rep):.0f}s; era total {st.median(seg_era):.0f}s")
for corr in sorted({r['corrida'] for r in it}):
    ss = [float(r["segundos_reloj"]) for r in it if r["corrida"] == corr]
    emite(f"   era {corr}: mediana {st.median(ss):.0f}s")

# resolución por era/repo
for corr in sorted({r['corrida'] for r in it}):
    rr = [r for r in it if r["corrida"] == corr]
    emite(f"   resolución {corr} ({rr[0]['condicion']}): {sum(1 for r in rr if r['resuelta']=='True')}/{len(rr)}")

with open(OUT / "qa06_verificacion_doc.txt", "w") as f:
    f.write("\n".join(lineas) + "\n")
