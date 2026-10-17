"""Auditoría 1 — muertes en el muro de tiempo (réplica 1).

Tres criterios cruzados:
  A) columna `muro` del CSV (replica1: umbral segundos_reloj >= 260, declarado en el diccionario del doc)
  B) log del arnés: lineas "agent timed out" del kernel log de réplica 1
  C) cruce A x resuelta / B x resuelta  ->  muertes entre fallos

Verifica además la identidad de las filas muro=True que no murieron (3278/3130 vs 3278/3043).
"""

import csv, re, json, sys
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
CSV = BASE / "analisis_c7/corridas_tareas.csv"
LOG = BASE / "data/replicas_c7/replica_1/c7-replica-condicion-7.log"

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
r1 = [r for r in rows if r["fuente"].startswith("replica1")]
assert len(r1) == 20, len(r1)

print("== A) Criterio CSV: columna muro (replica1: segundos_reloj >= 260) ==")
muro_csv = [r for r in r1 if r["muro"] == "True"]
print(f"muro=True: {len(muro_csv)}/20")
for r in sorted(muro_csv, key=lambda x: float(x["segundos_reloj"])):
    print(f"  {r['task_id']}: {float(r['segundos_reloj']):7.1f} s  resuelta={r['resuelta']}  clase={r['clase']}")

muro_csv_fallos = [r for r in muro_csv if r["resuelta"] == "False"]
print(f"muro=True y no resuelta (muerte por tiempo bajo criterio CSV): {len(muro_csv_fallos)}/16 fallos")
ids_csv_muerte = {r["task_id"] for r in muro_csv_fallos}
ids_csv_resueltas_muro = {r["task_id"] for r in muro_csv if r["resuelta"] == "True"}
print(f"  ids muro=True resueltas (falsos positivos de 'muerte'): {sorted(ids_csv_resueltas_muro)}")
ids_muro_true = {r["task_id"] for r in muro_csv}

print()
print("== B) Criterio log del arnés: 'agent timed out' en el kernel log ==")
txt = LOG.read_text(encoding="utf-8", errors="replace")
timeouts = sorted(set(re.findall(r"(?:Task|task)[^\n]*?(rich_\d+)[^\n]*?agent timed out", txt)))
# fallback: cualquier línea con 'agent timed out'
lineas = [l for l in txt.splitlines() if "agent timed out" in l]
ids_log = sorted(set(re.findall(r"rich_\d+", " ".join(lineas))))
print(f"lineas 'agent timed out': {len(lineas)}; ids únicos: {len(ids_log)}")
for i in ids_log:
    print(f"  {i}")
print(f"en muro=True (CSV) pero SIN timeout en log: {sorted(ids_muro_true - set(ids_log))}")
print(f"con timeout en log pero SIN muro=True (CSV): {sorted(set(ids_log) - ids_muro_true)}")

resueltas = {r["task_id"] for r in r1 if r["resuelta"] == "True"}
print(f"resueltas réplica 1: {sorted(resueltas)}")
log_muertes = [i for i in ids_log if i not in resueltas]
print(f"timeouts en log y no resueltas (muerte por tiempo, criterio log): {len(log_muertes)}/16 fallos")
log_resueltas_timeout = [i for i in ids_log if i in resueltas]
print(f"timeouts en log PERO resueltas (cosecha del árbol): {sorted(log_resueltas_timeout)}")

print()
print("== C) Síntesis ==")
n_fallos = sum(1 for r in r1 if r["resuelta"] == "False")
print(f"fallos totales: {n_fallos}")
print(f"CSV  muro>=260:            {len(muro_csv)}/20 tocó el muro | {len(muro_csv_fallos)}/{n_fallos} fallos")
print(f"LOG  'agent timed out':    {len(ids_log)}/20 tocó el muro | {len(log_muertes)}/{n_fallos} fallos")
print()
print("Verificación JSON crudo: resuelta/clase/segundos de 3130, 3043, 3278")
salida = json.load(open(BASE / "data/replicas_c7/replica_1/salida__c7_20261016T0459Z.json", encoding="utf-8"))
filas = salida["filas"]
for it in filas:
    if it["id"] in ("rich_3278", "rich_3130", "rich_3043"):
        print(f"  {it['id']}: resuelta={it['resuelta']} segundos_reloj={it['segundos_reloj']} "
              f"clase={it['clase']} llamadas_herramientas={it['llamadas_herramientas']}")
n_res = sum(1 for it in filas if it["resuelta"])
print(f"resueltas en JSON crudo: {n_res}/{len(filas)}")
