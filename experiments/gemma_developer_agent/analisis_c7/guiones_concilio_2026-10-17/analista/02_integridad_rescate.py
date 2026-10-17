"""Integridad del rescate: corridas_tareas.csv vs salidas crudas JSON.

Fuentes crudas:
- replica1: data/replicas_c7/replica_1/salida__c7_20261016T0459Z.json
- iteraciones: data/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-0{1,2,3}/salida__iteracion_0N.json
Tambien: tamanio de logs (0 bytes = faltante), huella replica1, cortado_por.
Salida: salida_02_integridad.txt
"""
import csv
import json
import os

BASE = "experiments/gemma_developer_agent"
DATA = f"{BASE}/data"
AN = f"{BASE}/analisis_c7"


def cargar_csv():
    return list(csv.DictReader(open(f"{AN}/corridas_tareas.csv", encoding="utf-8")))


def err_tool_count(anatomia):
    errs = anatomia.get("errores_de_herramienta") or {}
    return sum(int(v) for v in errs.values())


def bool_csv(v):
    return str(v).strip().lower() in ("true", "1")


def norm(v):
    s = str(v).strip()
    return "" if s in ("", "None", "null") else s


def main() -> None:
    out = []
    filas_csv = cargar_csv()
    out.append(f"corridas_tareas.csv: {len(filas_csv)} filas de datos")

    # ---- 1. logs y archivos crudos: existencia y tamano
    candidatos_log = [
        f"{DATA}/replicas_c7/replica_1/c7-replica-condicion-7.log",
        f"{DATA}/replicas_c7/replica_1/instalacion_error.txt",
    ]
    for n in ("01", "02", "03"):
        candidatos_log.append(
            f"{DATA}/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-{n}/log.txt"
        )
    out.append("\n== Integridad de archivos (0 bytes = faltante) ==")
    for p in candidatos_log:
        if os.path.exists(p):
            sz = os.path.getsize(p)
            out.append(f"  {p}: {sz} bytes {'<== FALTANTE' if sz == 0 else ''}")
        else:
            out.append(f"  {p}: NO EXISTE")

    # ---- 2. replica1 vs crudo
    r1 = json.load(open(f"{DATA}/replicas_c7/replica_1/salida__c7_20261016T0459Z.json"))
    out.append("\n== Replica 1 ==")
    out.append(
        f"  crudo: etiqueta={r1['etiqueta']} huella={r1['huella_config']} "
        f"tareas={r1['tareas']} cortado_por={r1['cortado_por']} sesion_s={r1['sesion_segundos']}"
    )
    csv_r1 = [f for f in filas_csv if f["fuente"] == "replica1_c7_4.5min"]
    out.append(f"  csv filas replica1: {len(csv_r1)}")
    crudo_por_id = {f["id"]: f for f in r1["filas"]}
    mism = 0
    for f in csv_r1:
        c = crudo_por_id.get(f["task_id"])
        if c is None:
            out.append(f"  FALTA en crudo: {f['task_id']}")
            mism += 1
            continue
        checks = [
            ("resuelta", str(c["resuelta"]), f["resuelta"]),
            ("clase", c["clase"], f["clase"]),
            ("segundos_reloj", str(c["segundos_reloj"]), f["segundos_reloj"]),
            ("llamadas_herramientas", str(c["llamadas_herramientas"]), f["llamadas_herramientas"]),
            ("llamadas_modelo", str(c["llamadas_modelo"]), f["llamadas_modelo"]),
        ]
        for nombre, crudo_val, csv_val in checks:
            if crudo_val != csv_val:
                out.append(f"  MISMATCH {f['task_id']}.{nombre}: crudo={crudo_val} csv={csv_val}")
                mism += 1
        muro_csv = bool_csv(f["muro"])
        muro_calc = c["segundos_reloj"] >= 260
        if muro_csv != muro_calc:
            out.append(f"  MURO mismatch {f['task_id']}: csv={muro_csv} recomputado={muro_calc}")
            mism += 1
    out.append(f"  diferencias replica1: {mism}")

    # ---- 3. iteraciones vs crudo
    out.append("\n== Iteraciones 2026-10-06 ==")
    tot_mism = 0
    for n in ("01", "02", "03"):
        p = f"{DATA}/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-{n}/salida__iteracion_{n}.json"
        d = json.load(open(p))
        out.append(f"  iteracion-{n}: completo={d.get('completo')}")
        for nombre, corrida in d["corridas"].items():
            fuente = f"iteracion_{n}_2026-10-06"
            csv_bloque = [
                f
                for f in filas_csv
                if f["fuente"] == fuente and f["corrida"] == nombre
            ]
            tareas_crudas = corrida["tareas"]
            out.append(
                f"    {nombre} (cond={corrida['condicion']}): crudo={len(tareas_crudas)} csv={len(csv_bloque)}"
            )
            crudo_ids = {t["instance_id"] for t in tareas_crudas}
            csv_ids = {f["task_id"] for f in csv_bloque}
            if crudo_ids != csv_ids:
                out.append(f"      ids solo-crudo: {sorted(crudo_ids - csv_ids)}")
                out.append(f"      ids solo-csv: {sorted(csv_ids - crudo_ids)}")
                tot_mism += 1
            for t in tareas_crudas:
                fc = [f for f in csv_bloque if f["task_id"] == t["instance_id"]]
                if not fc:
                    continue
                f = fc[0]
                ant = t.get("anatomia") or {}
                herr = ant.get("herramientas") or {}
                esperado = {
                    "resuelta": str(t["resuelta"]),
                    "clase": t["clase"],
                    "segundos_reloj": str(t["segundos_reloj"]),
                    "llamadas_herramientas": str(t["llamadas_herramientas"]),
                    "llamadas_modelo": str(t["llamadas_modelo"]),
                    "primera_edicion_llamada": norm(ant.get("llamada_de_la_primera_edicion", "")),
                    "err_tool_count": str(err_tool_count(ant)),
                    "usa_run_command": str(herr.get("run_command", 0)),
                    "usa_read_file": str(herr.get("read_file", 0)),
                    "usa_edit_file": str(herr.get("edit_file", 0)),
                    "usa_submit_patch": str(herr.get("submit_patch", 0)),
                }
                for k, ev in esperado.items():
                    if norm(f[k]) != ev:
                        out.append(f"      MISMATCH {nombre}/{t['instance_id']}.{k}: csv={f[k]!r} crudo={ev!r}")
                        tot_mism += 1
                muro_csv = bool_csv(f["muro"])
                muro_calc = t["segundos_reloj"] >= 230
                if muro_csv != muro_calc:
                    out.append(
                        f"      MURO mismatch {nombre}/{t['instance_id']}: csv={muro_csv} recomputado={muro_calc}"
                    )
                    tot_mism += 1
    out.append(f"  diferencias iteraciones: {tot_mism}")

    # ---- 4. tareas_features.csv vs tasks.jsonl crudo
    out.append("\n== tareas_features.csv vs data/tasks.jsonl ==")
    feats = list(csv.DictReader(open(f"{AN}/tareas_features.csv", encoding="utf-8")))
    out.append(f"  features: {len(feats)} filas")
    tj_path = f"{DATA}/tasks.jsonl"
    if os.path.exists(tj_path):
        tareas = [json.loads(l) for l in open(tj_path, encoding="utf-8")]
        out.append(f"  tasks.jsonl: {len(tareas)} tareas")
        por_id = {t.get("instance_id"): t for t in tareas}
        muestra = 0
        mismf = 0
        for f in feats:
            t = por_id.get(f["instance_id"])
            if t is None:
                mismf += 1
                if mismf < 5:
                    out.append(f"  sin tarea en tasks.jsonl: {f['instance_id']}")
                continue
            if muestra < 3:
                campos = list(t.keys())
                out.append(
                    f"  muestra campos tasks.jsonl: {campos[:12]}..."
                )
                muestra += 1
        out.append(f"  features sin match en tasks.jsonl: {mismf}")
    else:
        out.append(f"  {tj_path} NO EXISTE en local")

    res = "\n".join(out) + "\n"
    open("scratch/concilio-c7-fase4/analista-datos/salida_02_integridad.txt", "w").write(res)
    print(res)


if __name__ == "__main__":
    main()
