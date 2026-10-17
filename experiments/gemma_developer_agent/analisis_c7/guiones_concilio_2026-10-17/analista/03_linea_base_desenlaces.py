"""Linea base recontada + tabla de tiempos/desenlaces por corrida (minimo F3/F4 del rol).

Recomputa del CSV (verificado contra crudo en 02_integridad_rescate.py):
- resueltas por fuente/corrida y por clase de desenlace
- muertes en el muro de tiempo vs otras causas
- medianas de segundos_reloj y llamadas por corrida (vs tope conocido)
- tasa de submit (usa_submit_patch>0) en iteraciones; replica1 desde trazas (7/20)
- multiplicador wall-clock razonamiento vs no
Salida: salida_03_linea_base.txt
"""
import csv
from collections import Counter, defaultdict
from statistics import median, mean

AN = "experiments/gemma_developer_agent/analisis_c7"
filas = list(csv.DictReader(open(f"{AN}/corridas_tareas.csv", encoding="utf-8")))


def b(v):
    return str(v).strip().lower() in ("true", "1")


def stats(xs):
    xs = sorted(xs)
    return median(xs), mean(xs), max(xs)


def main():
    out = []
    r1 = [f for f in filas if f["fuente"].startswith("replica1")]
    it = [f for f in filas if f["fuente"].startswith("iteracion")]
    out.append(f"UNIVERSO: {len(filas)} filas = replica1 {len(r1)} + iteraciones {len(it)}")

    # --- resolucion por fuente
    out.append("\n== Resolucion ==")
    for nombre, bloque in (("replica1 (c7 razonamiento 4.5min)", r1), ("iteraciones (4min sin razonamiento)", it)):
        res = sum(b(f["resuelta"]) for f in bloque)
        out.append(f"  {nombre}: {res}/{len(bloque)} = {res/len(bloque)*100:.1f}%")
    res_it = sum(b(f["resuelta"]) for f in it)
    out.append(f"  combinado: {res_it+4}/{len(filas)} = {(res_it+4)/len(filas)*100:.1f}%")
    out.append("  por corrida:")
    for corr in sorted({f["corrida"] for f in filas}):
        bl = [f for f in filas if f["corrida"] == corr]
        res = sum(b(f["resuelta"]) for f in bl)
        cond = bl[0]["condicion"]
        out.append(f"    {corr} (cond={cond}): {res}/{len(bl)}")

    # --- clases de desenlace
    out.append("\n== Clases de desenlace ==")
    out.append(f"  replica1: {dict(Counter(f['clase'] for f in r1))}")
    out.append(f"  iteraciones: {dict(Counter(f['clase'] for f in it))}")

    # --- muro de tiempo
    out.append("\n== Muro de tiempo ==")
    m1 = [f for f in r1 if b(f["muro"])]
    m1_muertes = [f for f in m1 if not b(f["resuelta"])]
    out.append(
        f"  replica1: muro=True {len(m1)}/20; de ellas no resueltas (muertes) {len(m1_muertes)}/20 "
        f"({len(m1_muertes)/20*100:.0f}%)  [doc: 15/20 75%]"
    )
    med_all, mmean_all, _ = stats([float(f["segundos_reloj"]) for f in r1])
    med_m, mmean_m, _ = stats([float(f["segundos_reloj"]) for f in m1_muertes])
    out.append(
        f"  replica1 segundos_reloj: mediana {med_all} (doc: 272) media {mmean_all:.1f} (STATUS: 255) "
        f"| solo muertes-en-muro: mediana {med_m}"
    )
    mit = [f for f in it if b(f["muro"])]
    out.append(f"  iteraciones: muro=True {len(mit)}/148 [doc: 0/148 'bajo el umbral de 230 s']")
    ge230 = [f for f in it if float(f["segundos_reloj"]) >= 230]
    out.append(
        f"  iteraciones con segundos_reloj>=230: {len(ge230)}/148 "
        f"(clases: {dict(Counter(f['clase'] for f in ge230))})"
    )
    ge240 = [f for f in it if float(f["segundos_reloj"]) >= 240]
    out.append(f"  iteraciones con segundos_reloj>=240 (cap 4min): {len(ge240)}/148")

    # --- tabla por corrida: tiempos, llamadas vs tope
    out.append("\n== Tabla por corrida ==")
    out.append("corrida | n | resueltas | muro(muertes) | otras_no_resueltas | med s | media s | med llam | max llam | tope")
    for corr in sorted({f["corrida"] for f in filas}, key=lambda c: (c != "c7_20261016T0459Z", c)):
        bl = [f for f in filas if f["corrida"] == corr]
        n = len(bl)
        res = sum(b(f["resuelta"]) for f in bl)
        muro_muertes = sum(b(f["muro"]) and not b(f["resuelta"]) for f in bl)
        otras = n - res - muro_muertes
        secs = [float(f["segundos_reloj"]) for f in bl]
        calls = [int(f["llamadas_herramientas"]) for f in bl]
        tope = 60 if corr == "c7_20261016T0459Z" else 40
        md, mn, _ = stats(secs)
        out.append(
            f"  {corr} | {n} | {res} | {muro_muertes} | {otras} | {md} | {mn:.1f} | {median(calls)} | {max(calls)} | {tope}"
        )
    meds_it = []
    for corr in sorted({f["corrida"] for f in it}):
        bl = [f for f in it if f["corrida"] == corr]
        meds_it.append((corr, median(float(f["segundos_reloj"]) for f in bl)))
    out.append(f"\n  medianas iteraciones: {meds_it}  [doc: 79-93 s]")
    lo = min(m for _, m in meds_it)
    hi = max(m for _, m in meds_it)
    out.append(f"  multiplicador wall-clock (mediana replica1 {med_all} / mediana iter): x{med_all/hi:.1f}-x{med_all/lo:.1f}  [doc: x3-4]")
    mmedia_it = mean(float(f["segundos_reloj"]) for f in it)
    out.append(f"  por medias: {mmean_all:.0f} / {mmedia_it:.0f} = x{mmean_all/mmedia_it:.1f}")

    # --- tasa de submit
    out.append("\n== Tasa de submit ==")
    sub_it = sum(int(f["usa_submit_patch"] or 0) > 0 for f in it)
    out.append(
        f"  iteraciones (usa_submit_patch>0): {sub_it}/{len(it)} = {sub_it/len(it)*100:.0f}%  [doc: 91% 135/148]"
    )
    out.append("  replica1: sin columna anatomica en CSV; de las trazas ATIF (guion 02/manual):")
    out.append("    7/20 llamaron submit_patch con status ok (3130,3278,3296,3535,3675,3894,3905) -> 35%")
    out.append("    [doc: 'tasa de submit 20% (4/20)': NO reproducible como esta escrito; 4/20 = solo las no resueltas con submit ok]")

    open("scratch/concilio-c7-fase4/analista-datos/salida_03_linea_base.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
