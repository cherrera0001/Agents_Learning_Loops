"""Auditoría 5 — envelope de la cap de 12 h para max_time 9.0 min/tarea (y 6/10).

Supuestos declarados (los del propio expediente):
  N=120 tareas (~120 inferidas por el doc), setup 45 s/tarea, carga 367 s una vez,
  cap 720 min OFICIAL que INCLUYE setup (STATUS).
  Una tarea que muere en el muro consume el muro entero (sesion = max_time*60); el muro
  NO interrumpe una generación en curso (rich_3772: 573.7 s), así que esto es cota BAJA
  del coste de una muerte.
  Las tareas que no mueren consumen tiempos de la distribución EMPÍRICA de la era
  (148 segundos_reloj de iteraciones 2026-10-06). Ojo: la era tenía thinking oculto
  (budget 4096): es la mejor distribución disponible de "comportamiento no reasoning-on",
  pero NO mide thinking-off real (nunca corrido).

Modelo: total(f) = N*45 + 367 + suma de N tiempos, donde f*N tareas mueren (=muro s)
y el resto se bootstrapea de la era. 2000 sims con semilla.
"""

import csv, random, statistics as st
from pathlib import Path

BASE = Path("experiments/gemma_developer_agent")
rows = list(csv.DictReader(open(BASE / "analisis_c7/corridas_tareas.csv", encoding="utf-8")))
era = [float(r["segundos_reloj"]) for r in rows if r["fuente"].startswith("iteracion")]
assert len(era) == 148
era_sorted = sorted(era)
print(f"era: n=148 media={st.mean(era):.1f}s mediana={st.median(era):.1f}s "
      f"p90={era_sorted[int(0.9*148)]}s max={max(era)}s")
a_runs = [float(r["segundos_reloj"]) for r in rows if r["fuente"].startswith("iteracion") and r["corrida"] in ("A1","A2","A3","A4")]
print(f"era solo A1-A4 (condicion A): n={len(a_runs)} media={st.mean(a_runs):.1f}s mediana={st.median(a_runs):.1f}s")

N, SETUP_S, CARGA_S, CAP_MIN = 120, 45, 367, 720
FRA = (0.0, 0.074, 0.12, 0.25, 0.49, 0.5, 0.65, 0.75, 1.0)
CAPS = (4.5, 6.0, 9.0, 10.0)
rng = random.Random(20261017)

def simula(wall_min, f, base):
    wall_s = wall_min * 60
    n_mueren = round(f * N)
    tot = []
    for _ in range(2000):
        tareas = rng.choices(base, k=N - n_mueren) if n_mueren < N else []
        total_s = N * SETUP_S + CARGA_S + n_mueren * wall_s + sum(tareas)
        tot.append(total_s / 60)
    tot.sort()
    return st.mean(tot), tot[int(0.95 * len(tot))]

print()
print("== Mi envelope con distribución real (era 148; setup 45 s/tarea; carga 367 s; cap 720) ==")
for cap in CAPS:
    for f in FRA:
        m, p95 = simula(cap, f, era)
        print(f"  max_time {cap:>4} min, f={f:>5}: media {m:6.0f} min | p95 {p95:6.0f} -> {'CABE' if p95<=CAP_MIN else 'NO CABE'}")

print()
print("== Reproducción de las dos cuentas en disputa (f=0.75, cap 9.0) ==")
ext = 9.0 * 60 - 270
print(f"arquitecto: A3_off(314) + f*N*(cap-270)s/60 = 314 + 0.75*120*{ext}/60 = {314 + 0.75*120*ext/60:.0f} min  <- suma la EXTENSIÓN sobre 270 s")
directa = (N*SETUP_S + CARGA_S + 0.75*N*9.0*60 + 0.25*N*st.median(era)) / 60
print(f"directa (misma f, muro entero 540 s + era mediana {st.median(era):.0f} s): {directa:.0f} min")
media_era = st.mean(era)
breakeven_9 = ((CAP_MIN - (N*SETUP_S + CARGA_S)/60) * 60 / N - media_era) / (9.0*60 - media_era)
breakeven_6 = ((CAP_MIN - (N*SETUP_S + CARGA_S)/60) * 60 / N - media_era) / (6.0*60 - media_era)
print(f"break-even con era media {media_era:.0f} s: f*(9 min)={breakeven_9:.2f} | f*(6 min)={breakeven_6:.2f}")
breakeven_9_med = ((CAP_MIN - (N*SETUP_S + CARGA_S)/60) * 60 / N - st.median(era)) / (9.0*60 - st.median(era))
print(f"break-even con era mediana {st.median(era):.0f} s: f*(9 min)={breakeven_9_med:.2f}")

print()
print("== f observados ==")
print("f era a muro 240 s (clase tiempo_agotado): 11/148 = 0.074 | columna muro era (>=230): 18/148 = 0.122")
print("f réplica 1 (reasoning-on, muro 270): 13/20 = 0.65 por log | 15/20 = 0.75 por CSV")
print("f era 'estirado' a 540 s: desconocido (la era se cortó a 240; no sabemos cuántas habrían muerto a 540)")
