"""Recomputa la banda de ruido IC95 del score (doc C7 Q1, Fase 3).

Fuente: experiments/gemma_developer_agent/analisis_c7/envios.csv (derivado)
        experiments/gemma_developer_agent/submissions/registry.json (versionado, cruzar)
Universo: envíos con status=scored agrupados por sha256_12 del zip (mismo zip reenviado).
Salida: salida_01_ruido_ic95.txt
"""
import csv
import json
import math
from collections import defaultdict

BASE = "experiments/gemma_developer_agent"
AN = f"{BASE}/analisis_c7"


def main() -> None:
    rows = list(csv.DictReader(open(f"{AN}/envios.csv", encoding="utf-8")))
    scored = [r for r in rows if r["status"] == "scored" and r["public_score"] != ""]
    grupos = defaultdict(list)
    for r in scored:
        grupos[r["sha256_12"]].append(float(r["public_score"]))

    out = []
    out.append(f"envios.csv: {len(rows)} filas; scored con score: {len(scored)}")
    ss_within = 0.0
    n_total = 0
    for sha, xs in sorted(grupos.items()):
        n = len(xs)
        media = sum(xs) / n
        var = sum((x - media) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
        sd = math.sqrt(var)
        ss_within += sum((x - media) ** 2 for x in xs)
        n_total += n
        out.append(
            f"  zip {sha}: scores={xs} n={n} media={media:.4f} sd(muestral)={sd:.4f}"
        )
    # Estimador del documento: raiz de (SS dentro de grupo / (n_total - 1))
    sd_doc = math.sqrt(ss_within / (n_total - 1))
    # Pooled clasico (pesos por grados de libertad)
    sds = []
    for sha, xs in sorted(grupos.items()):
        n = len(xs)
        media = sum(xs) / n
        sds.append((n - 1, sum((x - media) ** 2 for x in xs)))
    sd_clasico = math.sqrt(sum(w * 0 + ss for w, ss in sds) / sum(w for w, _ in sds))
    ic95_doc = 1.96 * sd_doc
    ic95_clas = 1.96 * sd_clasico
    out.append("")
    out.append(f"SS_within={ss_within:.6f}  n_total={n_total} (incluye nav 648d312c)")
    out.append(f"sd 'agrupada' del documento = sqrt(SS_within/(n_total-1)) = {sd_doc:.4f}")
    out.append(f"  -> IC95 = +/-1.96*sd = +/-{ic95_doc:.4f}  (documento: 0.0207 -> +/-0.041)")
    out.append(f"sd pooled clasico (df) = {sd_clasico:.4f} -> IC95 = +/-{ic95_clas:.4f}")
    # Universo exacto del documento: solo los dos zips reenviados (65a02160, d8a3e1d3)
    ss_doc = 0.0
    n_doc = 0
    for sha in ("65a0216007e1", "d8a3e1d3558f"):
        xs = grupos[sha]
        m = sum(xs) / len(xs)
        ss_doc += sum((x - m) ** 2 for x in xs)
        n_doc += len(xs)
    sd_doc2 = math.sqrt(ss_doc / (n_doc - 1))
    out.append("")
    out.append(f"[universo doc: solo zips reenviados] SS={ss_doc:.6f} n={n_doc}")
    out.append(
        f"sd = sqrt(SS/(n-1)) = {sd_doc2:.4f} (doc: 0.0207) "
        f"-> IC95 = +/-{1.96 * sd_doc2:.4f} (doc: +/-0.041)"
    )
    sd_clas_doc = math.sqrt(ss_doc / (n_doc - 2))
    out.append(f"sd pooled clasico sobre los mismos 5 = {sd_clas_doc:.4f} -> +/-{1.96 * sd_clas_doc:.4f}")
    g1 = grupos.get("65a0216007e1", [])
    g2 = grupos.get("d8a3e1d3558f", [])
    out.append("")
    out.append(
        f"grupo 65a02160 (razonamiento): media={sum(g1)/len(g1):.3f} (doc: 0.113) "
        f"sd={math.sqrt(sum((x-sum(g1)/len(g1))**2 for x in g1)/(len(g1)-1)):.4f} (doc: 0.0289)"
    )
    out.append(
        f"grupo d8a3e1d3 (base 4min): media={sum(g2)/len(g2):.3f} (doc: 0.055) "
        f"sd={math.sqrt(sum((x-sum(g2)/len(g2))**2 for x in g2)/(len(g2)-1)):.4f} (doc: 0.0071)"
    )
    out.append("")
    out.append("Comparaciones del documento:")
    out.append(
        f"  sub-018 nav=0.10 vs viejo max=0.13: delta={0.13-0.10:.2f} "
        f"<= IC95_doc ({ic95_doc:.3f}) -> indistinguibles: {0.03 <= ic95_doc}"
    )
    reg = json.load(open(f"{BASE}/submissions/registry.json", encoding="utf-8"))
    entradas = reg if isinstance(reg, list) else reg.get("submissions", reg)
    texto = json.dumps(reg, ensure_ascii=False)
    for sha in ("65a02160", "d8a3e1d3"):
        out.append(f"  registry.json contiene {sha}: {sha in texto}")

    res = "\n".join(out) + "\n"
    open("scratch/concilio-c7-fase4/analista-datos/salida_01_ruido_ic95.txt", "w").write(res)
    print(res)


if __name__ == "__main__":
    main()
