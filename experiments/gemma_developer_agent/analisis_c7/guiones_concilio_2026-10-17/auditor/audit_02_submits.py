"""Auditoría 2 (v2) — submits de réplica 1 desde las trazas ATIF, parseando la estructura real:
steps[].tool_calls[].function_name + observation.content JSON con status.

Métricas: intento (>=1 llamada), ok (>=1 con status ok), resolución (JSON crudo).
Verificación: rich_3043 sin submit_patch + timeout en kernel + resuelta (cosecha del árbol).
"""

import json
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
TRACES = BASE / "data/replicas_c7/replica_1/results/c7_20261016T0459Z/traces"
LOG = BASE / "data/replicas_c7/replica_1/c7-replica-condicion-7.log"

def cuenta_submit(traza):
    n_intento = n_ok = 0
    for st in traza.get("steps", []):
        for tc in st.get("tool_calls", []):
            if tc.get("function_name") == "submit_patch":
                n_intento += 1
                obs = st.get("observation") or {}
                content = obs.get("content")
                try:
                    payload = json.loads(content) if isinstance(content, str) else (content or {})
                    if payload.get("status") == "ok":
                        n_ok += 1
                except Exception:
                    pass
    return n_intento, n_ok

detalle = {}
for t in sorted(TRACES.glob("trace_*.json")):
    tid = t.stem.replace("trace_", "")
    detalle[tid] = cuenta_submit(json.load(open(t, encoding="utf-8")))

intento = sorted(k for k, v in detalle.items() if v[0] > 0)
ok_ids = sorted(k for k, v in detalle.items() if v[1] > 0)
print(f"trazas: {len(detalle)}")
print(f"M_intento  (>=1 llamada submit_patch): {len(intento)}/20 -> {intento}")
print(f"M_ok       (>=1 submit_patch status ok): {len(ok_ids)}/20 -> {ok_ids}")

salida = json.load(open(BASE / "data/replicas_c7/replica_1/salida__c7_20261016T0459Z.json", encoding="utf-8"))
resueltas = sorted(it["id"] for it in salida["filas"] if it["resuelta"])
print(f"M_resolucion (resuelta=True): {len(resueltas)}/20 -> {resueltas}")
print()
print(" submits por tarea (n_intento, n_ok):")
for tid in sorted(detalle):
    marca = "  <- resuelta" if tid in resueltas else ""
    print(f"  {tid}: {detalle[tid]}{marca}")

print()
print("== rich_3043: cosecha del árbol ==")
print(f"  submit_patch en traza: {detalle['rich_3043'][0]} llamadas")
txt = LOG.read_text(encoding="utf-8", errors="replace")
hits = [l for l in txt.splitlines() if "rich_3043" in l and ("timed out" in l or "resuelta" in l)]
for l in dict.fromkeys(hits):
    print("  log:", l.strip()[:160])
fila = next(it for it in salida["filas"] if it["id"] == "rich_3043")
print(f"  JSON: resuelta={fila['resuelta']} segundos_reloj={fila['segundos_reloj']} llamadas={fila['llamadas_herramientas']}")
