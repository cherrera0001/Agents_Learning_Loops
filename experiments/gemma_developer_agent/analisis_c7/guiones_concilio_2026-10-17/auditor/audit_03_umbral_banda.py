"""Auditoría 3 — umbral 230 s en iteraciones (cifra 3) y banda A-vs-A (cifra 4).

Cifra 3: ¿cuántas de las 148 filas de iteraciones tienen segundos_reloj >= 230? ¿cuántas marca la
columna muro (iteraciones: umbral >=230)? ¿cuántas mueren por tiempo (clase tiempo_agotado_*)?

Cifra 4: corridas A1-A4 (misma config, mismas 15 rich): conteos resueltas, flips pareados,
IC95 de la banda de score (sd agrupada de envios.csv) y su traducción a tareas.
"""

import csv, itertools, statistics as st
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
CSV = BASE / "analisis_c7/corridas_tareas.csv"
ENVIOS = BASE / "analisis_c7/envios.csv"

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
era = [r for r in rows if r["fuente"].startswith("iteracion")]
assert len(era) == 148, len(era)

print("== Cifra 3: umbral 230 s en iteraciones (n=148) ==")
ge230 = [r for r in era if float(r["segundos_reloj"]) >= 230]
print(f"segundos_reloj >= 230: {len(ge230)}/148")
muro_col = [r for r in era if r["muro"] in ("True", "1")]
print(f"columna muro verdadera: {len(muro_col)}/148")
clase_tiempo = [r for r in era if r["clase"].startswith("tiempo_agotado")]
print(f"clase tiempo_agotado_*: {len(clase_tiempo)}/148")
otras_ge230 = sorted({r["clase"] for r in ge230 if not r["clase"].startswith("tiempo_agotado")})
print(f"clases de las >=230 s que no son tiempo_agotado: {otras_ge230}")
print("filas >=230 s por corrida:")
from collections import Counter
c = Counter(r["corrida"] for r in ge230)
for k, v in sorted(c.items()):
    print(f"  {k}: {v}")
print("medianas por corrida (s):")
med = {}
for corr in sorted({r["corrida"] for r in era}):
    ts = [float(r["segundos_reloj"]) for r in era if r["corrida"] == corr]
    med[corr] = st.median(ts)
    print(f"  {corr}: {st.median(ts):.1f} (n={len(ts)}, min={min(ts):.0f}, max={max(ts):.0f})")

print()
print("== Cifra 4: banda A-vs-A (A1..A4, mismas 15 rich) ==")
runs = {}
for corr in ("A1", "A2", "A3", "A4"):
    runs[corr] = {r["task_id"]: r["resuelta"] == "True" for r in era if r["corrida"] == corr}
    n = sum(runs[corr].values())
    print(f"  {corr}: {n}/15 resueltas -> {sorted(k for k,v in runs[corr].items() if v)}")
for a, b in itertools.combinations(("A1","A2","A3","A4"), 2):
    flips = sum(1 for t in runs[a] if runs[a][t] != runs[b][t])
    detalle = sorted(t for t in runs[a] if runs[a][t] != runs[b][t])
    print(f"  flips {a}<->{b}: {flips} {detalle}")
conteos = [sum(runs[c].values()) for c in ("A1","A2","A3","A4")]
print(f"conteos: {conteos}; rango: {max(conteos)-min(conteos)}")

print()
print("== IC95 banda de score (envios.csv) ==")
env = list(csv.DictReader(open(ENVIOS, encoding="utf-8")))
print("columnas:", env[0].keys())
for e in env[:25]:
    print(" ", {k: e[k] for k in list(e)[:8]})
