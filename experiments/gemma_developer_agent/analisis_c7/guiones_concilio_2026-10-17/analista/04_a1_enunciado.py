"""Anexo A1: riqueza del enunciado vs resolucion (join corridas_tareas x tareas_features).

Recomputa: mediana de enunciado_chars y patch_lineas en resueltas vs no resueltas (n=168).
Extra: medianas por repo en features (contexto del 'set rich de 138 chars'), y test A1
condicional en tareas con parche (las resueltas tienen parche mas corto ¿o son triviales?).
Salida: salida_04_a1.txt
"""
import csv
from statistics import median, mean

AN = "experiments/gemma_developer_agent/analisis_c7"
filas = list(csv.DictReader(open(f"{AN}/corridas_tareas.csv", encoding="utf-8")))
feats = {f["instance_id"]: f for f in csv.DictReader(open(f"{AN}/tareas_features.csv", encoding="utf-8"))}


def b(v):
    return str(v).strip().lower() in ("true", "1")


def main():
    out = []
    joined = []
    sin_feat = []
    for f in filas:
        ft = feats.get(f["task_id"])
        if ft is None:
            sin_feat.append(f["task_id"])
            continue
        joined.append((b(f["resuelta"]), int(ft["enunciado_chars"]), int(ft["patch_lineas"]), f))
    out.append(f"join corridas_tareas({len(filas)}) x tareas_features({len(feats)}): con match {len(joined)}; sin match {len(sin_feat)} {sorted(set(sin_feat))}")

    res = [j for j in joined if j[0]]
    nores = [j for j in joined if not j[0]]
    out.append(f"resueltas: {len(res)}; no resueltas: {len(nores)}  [doc A1: 29 vs 139, n=168]")
    for campo, idx, docval in (("enunciado_chars", 1, "1672 vs 159"), ("patch_lineas", 2, "16 vs 30")):
        mres = median(j[idx] for j in res)
        mno = median(j[idx] for j in nores)
        ares = mean(j[idx] for j in res)
        ano = mean(j[idx] for j in nores)
        out.append(
            f"  {campo}: mediana resueltas {mres} vs no {mno}  (medias {ares:.1f} vs {ano:.1f})  [doc: {docval}]"
        )
        # cociente
        out.append(f"    cociente medianas: {mres/max(mno,1):.1f}x  [doc A1: ~10x para enunciado]")

    # control: dentro de las NO resueltas, ¿la clase de desenlace cambia el enunciado?
    from collections import defaultdict
    por_clase = defaultdict(list)
    for r, chars, lines, f in joined:
        if not r:
            por_clase[f["clase"]].append(chars)
    out.append("\n  mediana enunciado_chars por clase (no resueltas):")
    for cl, xs in sorted(por_clase.items()):
        out.append(f"    {cl}: {median(xs)} (n={len(xs)})")

    # contexto: medianas por repo en features (doc/STATUS citan rich=138.5)
    por_repo = defaultdict(list)
    for ft in feats.values():
        por_repo[ft["repo"]].append(int(ft["enunciado_chars"]))
    out.append("\n  medianas enunciado_chars por repo (universo 129 tareas):")
    for repo, xs in sorted(por_repo.items()):
        out.append(f"    {repo}: {median(xs)} (n={len(xs)})  [STATUS: fastapi 677, rich 138.5, requests 406, httpx 243]")

    # implicacion del doc: 'optimizar sobre rich de 138 chars'
    rich = [int(ft["enunciado_chars"]) for ft in feats.values() if ft["repo"] == "Textualize/rich"]
    bajo300 = sum(1 for x in rich if x < 300)
    out.append(f"\n  rich con enunciado<300 chars: {bajo300}/{len(rich)}  [STATUS: '~20 (28 rich tienen <300)']")

    open("scratch/concilio-c7-fase4/analista-datos/salida_04_a1.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
