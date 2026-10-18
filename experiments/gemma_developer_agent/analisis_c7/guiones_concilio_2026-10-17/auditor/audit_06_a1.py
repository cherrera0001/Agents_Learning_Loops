"""Auditoría 6 — A1: riqueza del enunciado, resueltas vs no resueltas, dos denominadores.

Denominador fila (n=168): cada corrida×tarea es una fila; una tarea repetida cuenta multiple.
Denominador tarea única (n=48): una mediana por task_id sobre sus corridas (el analista usa n=48:
las 20 rich del set sustituto + ... verificamos cuántas task_id distintas hay en el join).
"""

import csv, statistics as st
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
rows = list(csv.DictReader(open(BASE / "analisis_c7/corridas_tareas.csv", encoding="utf-8")))
feat = {r["instance_id"]: r for r in csv.DictReader(open(BASE / "analisis_c7/tareas_features.csv", encoding="utf-8"))}

join = []
for r in rows:
    f = feat.get(r["task_id"])
    if f:
        join.append((r["task_id"], r["resuelta"] == "True", int(f["enunciado_chars"]), int(f["patch_lineas"])))
print(f"join fila-nivel: n={len(join)} (de {len(rows)} filas)")

res = [j for j in join if j[1]]
nres = [j for j in join if not j[1]]
print(f"filas resueltas: n={len(res)} | no resueltas: n={len(nres)}")
print(f"mediana enunciado_chars fila: resueltas {st.median(j[2] for j in res)} vs no {st.median(j[2] for j in nres)} "
      f"-> x{st.median(j[2] for j in res)/st.median(j[2] for j in nres):.1f}")
print(f"mediana patch_lineas fila:    resueltas {st.median(j[3] for j in res)} vs no {st.median(j[3] for j in nres)}")

# tasa fila-nivel por banda de enunciado
for corte in (1000,):
    r1 = sum(1 for j in res if j[2] >= corte) / len(res)
    r0 = sum(1 for j in nres if j[2] < corte) / len(nres)
    ge = sum(1 for j in join if j[2] >= corte)
    tasa_ge = sum(1 for j in join if j[2] >= corte and j[1]) / ge
    lt = sum(1 for j in join if j[2] < corte)
    tasa_lt = sum(1 for j in join if j[2] < corte and j[1]) / lt
    print(f"banda {corte}: tasa resolucion en filas con enunciado>={corte}: {tasa_ge:.2f} (n={ge}) vs <{corte}: {tasa_lt:.2f} (n={lt})")

# tarea única: mediana por task_id
from collections import defaultdict
por_tarea = defaultdict(list)
for tid, resuelta, enc, pl in join:
    por_tarea[tid].append((resuelta, enc, pl))
print(f"\ntask_id distintos en el join: {len(por_tarea)}")

def mediana_tarea(idds):
    encs, pls, fracc = [], [], []
    for tid in idds:
        vals = por_tarea[tid]
        encs.append(st.median(v[1] for v in vals))
        pls.append(st.median(v[2] for v in vals))
        fracc.append(sum(v[0] for v in vals) / len(vals))
    return encs, pls, fracc

# clasificación por tarea: resuelta si alguna corrida la resolvió (es la lectura del analista: n=48)
t_res = [t for t in por_tarea if any(v[0] for v in por_tarea[t])]
t_nres = [t for t in por_tarea if not any(v[0] for v in por_tarea[t])]
print(f"tarea única: resueltas (alguna vez) n={len(t_res)} | nunca resueltas n={len(t_nres)}")
e_r, p_r, f_r = mediana_tarea(t_res)
e_n, p_n, f_n = mediana_tarea(t_nres)
print(f"mediana enunciado_chars tarea: resueltas {st.median(e_r)} vs no {st.median(e_n)} -> x{st.median(e_r)/st.median(e_n):.1f}")
print(f"mediana patch_lineas tarea:    resueltas {st.median(p_r)} vs no {st.median(p_n)}")

# y si en vez de 'alguna vez', por fracción de corridas resueltas >= 0.5
t_res2 = [t for t in por_tarea if sum(v[0] for v in por_tarea[t]) / len(por_tarea[t]) >= 0.5]
t_nres2 = [t for t in por_tarea if sum(v[0] for v in por_tarea[t]) / len(por_tarea[t]) < 0.5]
e2, _, _ = mediana_tarea(t_res2)
e3, _, _ = mediana_tarea(t_nres2)
print(f"[sensibilidad, fracc>=0.5] resueltas n={len(t_res2)} vs no n={len(t_nres2)}: "
      f"{st.median(e2)} vs {st.median(e3)} -> x{st.median(e2)/st.median(e3):.1f}")
