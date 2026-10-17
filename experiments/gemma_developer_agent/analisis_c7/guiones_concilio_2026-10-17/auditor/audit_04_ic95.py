"""Auditoría 4 — banda de ruido IC95 desde envios.csv (solo envíos scored de zips reenviados)."""

import csv, math
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
env = list(csv.DictReader(open(BASE / "analisis_c7/envios.csv", encoding="utf-8")))

# reenvíos del mismo zip: 65a02160 (x3: 0.08/0.13/0.13), d8a3e1d3 (x2: 0.06/0.05)
grupos = {}
for e in env:
    if e["status"] == "scored" and e["public_score"]:
        grupos.setdefault(e["sha256_12"], []).append(float(e["public_score"]))
for k, v in grupos.items():
    print(k, v)

sel = {k: v for k, v in grupos.items() if len(v) >= 2}
print("grupos con reenvíos:", {k: v for k, v in sel.items()})

allv = [x for v in sel.values() for x in v]
n = len(allv)
# estimador del documento: sqrt(SS_dentro/(n-1))
ss = sum(sum((x - sum(v)/len(v))**2 for x in v) for v in sel.values())
sd_doc = math.sqrt(ss / (n - 1))
# pooled clásico: SS/(n-k)
k = len(sel)
sd_pool = math.sqrt(ss / (n - k))
print(f"n={n}, k={k}, SS_dentro={ss:.6f}")
print(f"estimador doc  sqrt(SS/(n-1)) = {sd_doc:.4f} -> IC95 (1.96*sd) = ±{1.96*sd_doc:.4f}")
print(f"pooled clásico sqrt(SS/(n-k)) = {sd_pool:.4f} -> ±{1.96*sd_pool:.4f} | IC95 de la media t(3)=3.182: ±{3.182*sd_pool/math.sqrt(n):.4f}")
# incluyendo nav (sub-018 0.10) y el viejo 0.13 (65a02160) como tercer grupo del mismo kit base
sel2 = dict(sel)
nav = grupos.get("648d312cd534")
if nav:
    sel2["nav+base"] = nav + grupos.get("01a6d82fc42d", []) + grupos.get("4ac5ac329aad", [])
    allv2 = [x for v in sel2.values() for x in v]
    ss2 = sum(sum((x - sum(v)/len(v))**2 for x in v) for v in sel2.values())
    sd2 = math.sqrt(ss2 / (len(allv2) - 1))
    print(f"incluyendo nav/base: grupos={ {kk: len(vv) for kk, vv in sel2.items()} } sd={sd2:.4f} -> ±{1.96*sd2:.4f}")

print()
print("traducción a tareas (denominador 58): 1 tarea = 1/58 =", round(1/58, 4))
for d in (2, 3, 4, 5):
    print(f"  Δ{d} flips = {d/58:.3f} en score; ¿dentro de ±0.041? {d/58 <= 0.041}")
