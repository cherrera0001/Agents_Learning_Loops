---
name: corrida-valida
description: Comprobar que una corrida de un experimento con modelo dejó en disco lo necesario para explicar su resultado, y que una decisión se apoya en evidencia suficiente.
---

# Corrida válida y decisión válida

> **Skill de entorno** ([glosario](../../docs/entorno/glosario.md), término 5). **No es un nodo Skill de
> la memoria**. La usa el staff de experimento: no es el agente de biblioteca ni el solver acotado, y no
> cambia el algoritmo.

## Fuente

- [`CONTRIBUTING.md`](../../CONTRIBUTING.md#vuelta-de-un-experimento-con-modelo), *Vuelta de un
  experimento con modelo*: el criterio que esta skill proyecta, aprobado por el dueño el 2026-10-08.
- [`skills/proteger-evidencia`](../proteger-evidencia/SKILL.md): quien comprueba lee los archivos de una
  corrida; no los modifica.
- Episodio: `learning/episodes/065-issue-103-vuelta-39-concilio-y-registro.json`. Se dijo que cinco
  corridas traían «dos logs por tarea» mirando que los archivos existían: 155 de los 290 pesaban 0 bytes.
  Se dijo que un envío «dio error dos veces» con una sola lectura: a los 24 minutos tenía nota.

## Cuándo

- Al bajar lo que dejó una corrida o un envío, antes de leer su resultado.
- Antes de conservar o descartar una condición.
- Antes de subir, enviar o pagar algo que dependa de una corrida anterior.

## Procedimiento

1. **Baja y demuestra.** Ejecuta el guion de rescate del experimento y anota el código de salida, la hora
   UTC y la ruta. La prueba del rescate es una lista de archivos con sus bytes y líneas, también de lo que
   hay dentro de los archivos comprimidos; no es un relato.
2. **Un archivo de 0 bytes es un faltante.** Si un archivo exigido pesa 0 bytes, la corrida no cumple y
   el rescate se informa como parcial, aunque el guion haya salido con 0.
3. **Comprueba cada tarea contra el criterio de corrida válida** de `CONTRIBUTING.md`: traza, parche,
   salida de pruebas, motivo de fin aunque la tarea se resuelva, y la última petición en vuelo. Lista lo
   que falta por tarea. Una corrida que no cumple se usa como exploración, no como base de una decisión.
4. **Lee dos veces el estado de lo remoto.** El estado de un envío o de una corrida remota puede cambiar.
   Guarda cada lectura con su hora. Un error genérico de la plataforma se anota «sin lectura» y se vuelve
   a leer en el rescate siguiente; no cuenta como refutación de una predicción.
5. **Un envío es una nota, no una corrida.** Solo se envía una condición que ya tiene una corrida válida.
6. **Antes de decidir, aplica el criterio de decisión válida:** predicción previa con su umbral, el mismo
   conjunto de tareas en los dos brazos, el tamaño mínimo o el número mínimo de pares discordantes que
   fija el criterio, la prueba exacta y una repetición de la base. Con menos, el resultado se anota
   «exploratorio» y no cambia la configuración vigente.
7. **Di qué no dejó rastro.** Cada informe de una corrida termina con la lista de eventos de fallo que no
   quedaron en ningún archivo.

## Qué no hace

- No relaja la regla de que nada se sube ni se envía sin la orden del dueño.
- No convierte una corrida sin rastro en válida por haber dado un buen número.
