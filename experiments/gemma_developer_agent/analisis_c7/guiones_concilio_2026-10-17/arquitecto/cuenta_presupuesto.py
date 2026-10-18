"""Cuenta del arquitecto de IA para el informe C7-Fase 4 (solo aritmética, sin datos nuevos).

Toda entrada sale de documentos del repo, citados en el informe. Nada se recomputa de series;
esto es el envelope (casos esperado / estresado / peor) de la cap oficial de 12 h y un boceto de
potencia del contraste de 5 brazos. Unidad: minutos de reloj de la corrida de evaluación.
"""

from math import sqrt, comb, erf

# ---- Entradas citadas -------------------------------------------------------
# c7_analisis_critico.md A3 (líneas 160-166): reasoning-on 607 min (p95 638) de 720;
# sin razonamiento 314 (p95 336). Setup 45 s/tarea + 7 min de carga, una vez.
# STATUS.md línea 29: peor caso kit v2 5.0 min = 120*300 + 120*45 + 367 = 698 min <= 720.
# c7_analisis_critico.md Q1 (línea 57): era 4 min sin razonamiento, mediana 79-93 s, 0/148 > 230 s.
N_TAREAS = 120          # "las ~120 tareas caben" (c7_analisis_critico.md línea 48)
SETUP_S = 45            # STATUS.md línea 22 (warm pooling 0-45 s; A3 usa 45)
CARGA_S = 367           # STATUS.md línea 19 (réplica 1, L4; la nota vieja daba hasta 1142)
A3_ON = 607             # c7_analisis_critico.md línea 161
A3_OFF = 314            # c7_analisis_critico.md línea 163
CAP = 720

print("== 1. Envelope de la cap de 12 h (minutos) ==")
print(f"A3 reportado: reasoning-on {A3_ON} (p95 638) | thinking-off {A3_OFF} (p95 336) | cap {CAP}")
print(f"Envelope propio thinking-off: 120*(79..93)s = {120*79/60:.0f}-{120*93/60:.0f} min "
      f"+ setup {N_TAREAS*SETUP_S/60:.0f} + carga {CARGA_S/60:.1f} "
      f"= {120*79/60 + N_TAREAS*SETUP_S/60 + CARGA_S/60:.0f}-"
      f"{120*93/60 + N_TAREAS*SETUP_S/60 + CARGA_S/60:.0f} min (cola del set sustituto puede subirlo a ~{A3_OFF})")
for cap_min in (4.5, 5.0, 6.0, 9.0, 10.0):
    worst = N_TAREAS * (cap_min * 60 + SETUP_S) / 60 + CARGA_S / 60
    print(f"  max_time {cap_min:>4}: peor caso (todas al muro) = {worst:7.0f} min -> "
          f"{'CABE' if worst <= CAP else 'NO CABE'}")
print("  Estresado: total(f) = A3_off + f*120*(extension media del muro); extension = cap-270 s")
for cap_min in (6.0, 9.0, 10.0):
    ext = cap_min * 60 - 270
    for f in (0.2, 0.5, 0.75, 1.0):
        tot = A3_OFF + f * N_TAREAS * ext / 60
        print(f"    cap {cap_min:>4}, f={f:>4}: {tot:6.0f} min -> {'CABE' if tot <= CAP else 'NO CABE'}")

print()
print("== 2. Boceto de potencia del contraste (n=20 por brazo, un run) ==")
p = 0.2  # tasa observada de A (4/20)
sd_diff = sqrt(2 * p * (1 - p) / 20)
print(f"sd de la diferencia entre dos brazos iguales Binomial(20, {p}) = {sd_diff:.3f} = {sd_diff*20:.1f} tareas")
for lead in (2, 3, 4, 5, 6):
    d = lead / 20
    z = d / sd_diff
    p2 = 1 - erf(z / sqrt(2))
    print(f"  ventaja de {lead} tareas = {d:.2f} = {z:.1f} sigma -> p dos colas ~ {p2:.3f}")
print("  McNemar exacto (pares discordantes limpios, solo victorias del brazo):")
for wins in (3, 4, 5, 6):
    p_one = 0.5 ** wins  # P(k o mas en una direccion) con n=k discordantes = 2 * sum_{i>=k} C(k,i) 2^-k = 2*2^-k
    pval = min(1.0, 2 * 0.5**wins)
    print(f"    {wins}-0 discordantes: p = {pval:.4f}")
print()
coste = 7 * 93 / 60
print(f"== 3. Coste lunes: 7 x 93 min = {coste:.2f} h (STATUS.md línea 231) ==")
print(f"   peor caso por corrida: 20*270 + 20*45 + 1142 s = {(20*270+20*45+1142)/60:.0f} min "
      f"-> 7 corridas = {7*(20*270+20*45+1142)/60/60:.1f} h (sigue <= 30 h)")
print(f"   con un 6.º brazo (thinking-off + 9 min): esperado ~1.5 h, peor {(20*540+20*45+1142)/60:.0f} min = "
      f"{(20*540+20*45+1142)/60/60:.1f} h -> total peor {7*(20*270+20*45+1142)/60/60 + (20*540+20*45+1142)/60/60:.1f} h")
