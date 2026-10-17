"""Anexo A4: leaderboard completo (descarga oficial 2026-10-17 15:01 UTC).

Fuente: /tmp/lb_c7/gemma-4-developer-agent-publicleaderboard-2026-10-17T15:01:23.csv
        (3.043 equipos; NO comiteada en el repo, hallada solo en /tmp del mismo dia)
Recomputa: mediana/media/p25/p75/p90, cabeza (conteo por score), n con >=0.13,
posicion relativa de 0.13 y 0.10.
Salida: salida_07_a4_leaderboard.txt
"""
import csv
from statistics import median, mean

LB = "/tmp/lb_c7/gemma-4-developer-agent-publicleaderboard-2026-10-17T15:01:23.csv"


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def main():
    out = []
    rows = list(csv.DictReader(open(LB, encoding="utf-8-sig")))
    scores = [float(r["Score"]) for r in rows]
    n = len(scores)
    out.append(f"equipos: {n}  [doc A4: 3.043]")
    out.append(f"mediana {median(scores):.2f} (doc 0.13) | media {mean(scores):.3f} (doc 0.119)")
    out.append(
        f"p25 {pct(scores,25):.2f} (doc 0.08) | p75 {pct(scores,75):.2f} (doc 0.17) | p90 {pct(scores,90):.2f} (doc 0.18)"
    )
    from collections import Counter
    cabeza = Counter()
    for s in scores:
        cabeza[round(s, 2)] += 1
    out.append("\nconteo por score (top de la distribucion):")
    for s in sorted(cabeza, reverse=True)[:12]:
        out.append(f"  {s:.2f}: {cabeza[s]} equipos")
    doc_cabeza = {0.24: 2, 0.22: 27, 0.20: 95, 0.18: 317, 0.17: 401, 0.15: 412, 0.13: 344}
    out.append("")
    for s, esperado in doc_cabeza.items():
        real = cabeza.get(s, 0)
        out.append(f"  {s:.2f}: doc {esperado} vs recomputado {real} {'OK' if esperado==real else 'DIFF'}")
    n013 = sum(1 for s in scores if s >= 0.13)
    out.append(f"\ncon >=0.13: {n013} equipos (doc 1.598); top {n013/n*100:.0f}% (doc ~52%)")
    n010 = sum(1 for s in scores if s >= 0.10)
    out.append(f"con >=0.10: {n010} equipos")
    # posicion de nuestros scores
    mejor = next(r for r in rows if r["TeamName"] == "Yurnero")
    out.append(f"\ntop1: {mejor['TeamName']} {mejor['Score']}")
    out.append("nuestro 0.13 (kit viejo): exactamente la mediana" if median(scores) == 0.13 else "")
    out.append(f"score 0.10 (sub-018): percentil {sum(1 for s in scores if s < 0.10)/n*100:.0f}")
    # pasos de cuantizacion observados
    vals = sorted(set(scores), reverse=True)[:15]
    out.append(f"\nprimeros scores unicos: {vals}")
    diffs = sorted({round(vals[i]-vals[i+1],4) for i in range(len(vals)-1)})
    out.append(f"diffs entre top: {diffs}  [doc: pasos ~0.02; 1/58=0.0172]")
    open("scratch/concilio-c7-fase4/analista-datos/salida_07_a4_leaderboard.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
