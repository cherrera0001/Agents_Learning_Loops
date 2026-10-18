"""Anexo A2: conducta asociada a resolver (primera edicion, errores de herramienta).

Recomputa desde el CRUDO (anatomia de salida__iteracion_0N.json), universo: filas de
iteraciones con llamada_de_la_primera_edicion != None. Cruzar con CSV ya verificado (02).
Recomputa tambien desde el CSV solo, para mostrar que el derivado cuadra con el crudo.
Salida: salida_05_a2.txt
"""
import csv
import json
from statistics import median, mean

DATA = "experiments/gemma_developer_agent/data"
AN = "experiments/gemma_developer_agent/analisis_c7"


def err_count(anatomia):
    errs = anatomia.get("errores_de_herramienta") or {}
    return sum(int(v) for v in errs.values())


def main():
    out = []
    # ---- crudo
    crudo = []
    for n in ("01", "02", "03"):
        p = f"{DATA}/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-{n}/salida__iteracion_{n}.json"
        d = json.load(open(p))
        for corr, c in d["corridas"].items():
            for t in c["tareas"]:
                ant = t.get("anatomia") or {}
                crudo.append(
                    {
                        "corrida": corr,
                        "task": t["instance_id"],
                        "resuelta": t["resuelta"],
                        "pe": ant.get("llamada_de_la_primera_edicion"),
                        "err": err_count(ant),
                    }
                )
    con_pe = [c for c in crudo if c["pe"] is not None]
    sin_pe = [c for c in crudo if c["pe"] is None]
    out.append(f"CRUDO iteraciones: {len(crudo)} tareas; con primera_edicion: {len(con_pe)}; sin: {len(sin_pe)}")
    out.append(f"  [doc A2: 'n=103 con primera edicion']")
    res = [c for c in con_pe if c["resuelta"]]
    nores = [c for c in con_pe if not c["resuelta"]]
    out.append(f"  resueltas: {len(res)}; no resueltas: {len(nores)}")
    out.append(
        f"  primera_edicion mediana: resueltas {median(c['pe'] for c in res)} vs no {median(c['pe'] for c in nores)}  [doc: 5 vs 20]"
    )
    out.append(
        f"  primera_edicion media: resueltas {mean(c['pe'] for c in res):.1f} vs no {mean(c['pe'] for c in nores):.1f}"
    )
    out.append(
        f"  errores herramienta media: resueltas {mean(c['err'] for c in res):.2f} vs no {mean(c['err'] for c in nores):.2f}  [doc: 1.7 vs 2.4]"
    )
    out.append(
        f"  errores herramienta mediana: resueltas {median(c['err'] for c in res)} vs no {median(c['err'] for c in nores)}"
    )
    # entre las no resueltas, ¿quienes no editaron nunca?
    nores_sin_editar = len(sin_pe)
    nores_con_editar = len(nores)
    out.append(f"  no resueltas sin ninguna edicion: {nores_sin_editar}; con edicion: {nores_con_editar}")

    # ---- CSV derivado (debe cuadrar)
    filas = list(csv.DictReader(open(f"{AN}/corridas_tareas.csv", encoding="utf-8")))
    it = [f for f in filas if f["fuente"].startswith("iteracion") and f["primera_edicion_llamada"] not in ("", "None")]
    res_c = [f for f in it if f["resuelta"] == "True"]
    nores_c = [f for f in it if f["resuelta"] != "True"]
    out.append(f"\nCSV iteraciones con primera_edicion: {len(it)}")
    out.append(
        f"  medianas: {median(int(f['primera_edicion_llamada']) for f in res_c)} vs {median(int(f['primera_edicion_llamada']) for f in nores_c)}"
    )
    out.append(
        f"  err medias: {mean(int(f['err_tool_count']) for f in res_c):.2f} vs {mean(int(f['err_tool_count']) for f in nores_c):.2f}"
    )

    # ---- replica1 desde trazas ATIF (complemento; la edicion temprana aplica tambien)
    import glob, os
    base = f"{DATA}/replicas_c7/replica_1/results/c7_20261016T0459Z"
    por_tarea = {}
    resueltas_r1 = {"rich_3894", "rich_3278", "rich_3905", "rich_3043"}
    for tp in sorted(glob.glob(base + "/traces/trace_*.json")):
        tid = os.path.basename(tp)[6:-5]
        d = json.load(open(tp))
        llamada = 0
        first_edit = None
        for s in d["steps"]:
            if s.get("source") != "agent":
                continue
            for tc in (s.get("tool_calls") or []):
                llamada += 1
                if tc.get("function_name") == "edit_file" and first_edit is None:
                    first_edit = llamada
        por_tarea[tid] = first_edit
    con = {t: v for t, v in por_tarea.items() if v is not None}
    res_pe = [v for t, v in con.items() if t in resueltas_r1]
    nores_pe = [v for t, v in con.items() if t not in resueltas_r1]
    out.append(f"\nReplica1 (trazas ATIF): con edicion {len(con)}/20")
    if res_pe and nores_pe:
        out.append(f"  primera_edicion mediana: resueltas {median(res_pe)} (n={len(res_pe)}) vs no {median(nores_pe)} (n={len(nores_pe)})")

    open("scratch/concilio-c7-fase4/analista-datos/salida_05_a2.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
