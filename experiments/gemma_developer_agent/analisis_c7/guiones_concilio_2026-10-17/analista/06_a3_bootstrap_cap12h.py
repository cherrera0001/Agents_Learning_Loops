"""Anexo A3: simulacion bootstrap de la cap de 12 h (REEJECUCION; el guion original no se comitio).

Reconstruccion fiel a la descripcion del documento: 'bootstrap sobre tiempos reales por
tarea, 2.000 simulaciones, setup 45 s/tarea + 7 min una vez', N=120 tareas (la proyeccion
oficial de STATUS usa 120: 540-637 min de 720). Se verifica contra los numeros del doc:
razonamiento-on media 607 (p95 638); thinking-off media 314 (p95 336).

Escenarios:
  A) razonamiento-on : muestrea 120 tiempos de replica1 (20 tiempos reales, con reemplazo)
  B) thinking-off    : muestrea 120 tiempos de las 10 corridas 2026-10-06 (148 tiempos)
  C) thinking-off x2 : tiempos duplicados (reinversion: 4.5 -> 9-10 min/tarea)
Sensibilidad: N=129; setup con carga real 367 s en vez de 7 min; censura a 300 s/tarea
(el harness real corta la tarea: sin censura la simulacion sobrestima el peor caso).
Salida: salida_06_a3_bootstrap.txt
"""
import random
from statistics import mean, median

random.seed(20261017)
DATA = "experiments/gemma_developer_agent/data"
N_SIM = 2000
N_TAREAS = 120
SETUP_POR_TAREA_S = 45
CARGA_MIN = 7.0
CAP_MIN = 720.0


def cargar_tiempos():
    import json

    r1 = json.load(open(f"{DATA}/replicas_c7/replica_1/salida__c7_20261016T0459Z.json"))
    t_on = [f["segundos_reloj"] for f in r1["filas"]]
    t_off = []
    for n in ("01", "02", "03"):
        d = json.load(open(f"{DATA}/rescate_kaggle/2026-10-06T1910Z/notebooks/iteracion-{n}/salida__iteracion_{n}.json"))
        for c in d["corridas"].values():
            t_off.extend(t["segundos_reloj"] for t in c["tareas"])
    return t_on, t_off


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def sim(tiempos, n_tareas, factor, censura=None, carga_min=CARGA_MIN):
    totales = []
    base = sum(tiempos) / len(tiempos)
    for _ in range(N_SIM):
        muestra = random.choices(tiempos, k=n_tareas)
        s = 0.0
        for t in muestra:
            t *= factor
            if censura is not None and t > censura:
                t = censura
            s += t
        total_min = s / 60 + n_tareas * SETUP_POR_TAREA_S / 60 + carga_min
        totales.append(total_min)
    return totales


def resumen(nombre, totales):
    exceso = sum(1 for t in totales if t > CAP_MIN) / len(totales) * 100
    linea = (
        f"  {nombre}: media {mean(totales):.0f} (doc?) | mediana {median(totales):.0f} "
        f"| p5 {pct(totales,5):.0f} | p95 {pct(totales,95):.0f} | max {max(totales):.0f} "
        f"| P(>720) {exceso:.1f}%"
    )
    return linea, mean(totales), pct(totales, 95)


def main():
    t_on, t_off = cargar_tiempos()
    out = []
    out.append(f"tiempos reales: razonamiento-on n={len(t_on)} media={mean(t_on):.1f}s mediana={median(t_on)}s")
    out.append(f"                thinking-off   n={len(t_off)} media={mean(t_off):.1f}s mediana={median(t_off)}s")
    out.append(f"N_SIM={N_SIM} N_TAREAS={N_TAREAS} setup={SETUP_POR_TAREA_S}s/tarea carga={CARGA_MIN}min")
    out.append(f"check aritmetico: 120*{mean(t_on):.1f}/60+90+7 = {120*mean(t_on)/60+97:.1f} (doc: 607)")
    out.append(f"                  120*{mean(t_off):.1f}/60+90+7 = {120*mean(t_off)/60+97:.1f} (doc: 314)")
    out.append("")
    out.append("[doc A3: razonamiento-on 607 (p95 638); thinking-off 314 (p95 336); slack ~406]")
    out.append("")
    r = {}
    linea, m, p95 = resumen("A razonamiento-on (replica1 x120)", sim(t_on, N_TAREAS, 1))
    out.append(linea); r["A"] = (m, p95)
    linea, m, p95 = resumen("B thinking-off (iteraciones x120)", sim(t_off, N_TAREAS, 1))
    out.append(linea); r["B"] = (m, p95)
    linea, m, p95 = resumen("C thinking-off x2 tiempos (9-10 min/t)", sim(t_off, N_TAREAS, 2))
    out.append(linea); r["C"] = (m, p95)
    out.append("")
    out.append("Sensibilidad:")
    linea, m, p95 = resumen("A2 razon-on, N=129", sim(t_on, 129, 1))
    out.append(linea)
    linea, m, p95 = resumen("B2 thinking-off, N=129", sim(t_off, 129, 1))
    out.append(linea)
    linea, m, p95 = resumen("A3 razon-on, carga real 367s", sim(t_on, N_TAREAS, 1, carga_min=367/60))
    out.append(linea)
    linea, m, p95 = resumen("A4 razon-on, censura 300s/tarea", sim(t_on, N_TAREAS, 1, censura=300))
    out.append(linea)
    linea, m, p95 = resumen("C2 thinking-off x2, censura 300s/t", sim(t_off, N_TAREAS, 2, censura=300))
    out.append(linea)
    out.append("")
    out.append(f"slack thinking-off (doc ~406): 720-{r['B'][0]:.0f} = {720-r['B'][0]:.0f} min")
    out.append(f"escenario C (x2 tiempo) cabe: media {r['C'][0]:.0f} <= 720: {r['C'][0] <= 720} (p95 {r['C'][1]:.0f})")
    open("scratch/concilio-c7-fase4/analista-datos/salida_06_a3_bootstrap.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
