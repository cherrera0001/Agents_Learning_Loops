"""Auditoría 7 — verificaciones menores de decisiones:

a) mediana/media de segundos_reloj réplica 1 (doc: mediana 272 s, media 255.2)
b) cluster de segundos_reloj: ¿los 13 timeouts del log separan de 3278/3130?
c) sensibilidad 'incluyendo nav ±0.036' del analista: ¿artefacto de dilución?
"""

import csv, re, statistics as st, math
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
rows = list(csv.DictReader(open(BASE / "analisis_c7/corridas_tareas.csv", encoding="utf-8")))
r1 = [r for r in rows if r["fuente"].startswith("replica1")]
t = sorted(float(r["segundos_reloj"]) for r in r1)
print(f"a) replica1 segundos_reloj: mediana {st.median(t):.1f} s | media {st.mean(t):.1f} s")
print(f"   sorted: {[f'{x:.1f}' for x in t]}")

print()
print("b) cluster: timeouts del log vs no-timeouts (muro=True)")
LOG = BASE / "data/replicas_c7/replica_1/c7-replica-condicion-7.log"
txt = LOG.read_text(encoding="utf-8", errors="replace")
ids_log = set(re.findall(r"rich_\d+", " ".join(l for l in txt.splitlines() if "agent timed out" in l)))
for r in sorted(r1, key=lambda x: float(x["segundos_reloj"])):
    flag = "timeout-log" if r["task_id"] in ids_log else "sin-timeout"
    if float(r["segundos_reloj"]) > 250 or r["task_id"] in ids_log:
        print(f"   {r['task_id']} {float(r['segundos_reloj']):6.1f} s {flag} resuelta={r['resuelta']}")

print()
print("c) sensibilidad de banda 'incluyendo nav'")
ss = 0.001717  # SS_dentro de los 5 reenvíos (audit_04)
n0 = 5
print(f"   5 reenvíos: sd={math.sqrt(ss/(n0-1)):.4f} -> ±{1.96*math.sqrt(ss/(n0-1)):.4f}")
n1 = 6  # añadiendo un solo punto (nav 0.10) como 'grupo' de 1: aporta 0 al SS_dentro
print(f"   +1 punto (nav): sd={math.sqrt(ss/(n1-1)):.4f} -> ±{1.96*math.sqrt(ss/(n1-1)):.4f}  <- solo diluye n; el punto no aporta varianza")
