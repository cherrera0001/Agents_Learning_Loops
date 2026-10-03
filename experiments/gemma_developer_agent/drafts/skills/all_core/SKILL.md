# Borrador Exploratorio de Directivas de Inspección

> [!NOTE]
> Este archivo es un apunte redactado a mano de directivas de inspección.
> **No representa una skill consolidada** (no proviene de episodios de minería previa) **ni un control
> placebo** (el placebo B se formulará como texto neutral emparejado en longitud una vez que C esté
> definida).

## Propósito
Conservar notas exploratorias sobre flujos de trabajo con herramientas de grafo y reproducción de fallos.

## Directivas Exploratorias
1. Para tareas de FastAPI, Rich o Requests, revisar primero la traza de fallo del test de reproducción
   mediante `run_command(command="pytest <test_file>")`.
2. Usar `get_code_neighbors(node)` para ubicar funciones que llaman o son llamadas por el símbolo que arroja
   el error, evitando búsquedas basadas únicamente en palabras clave del reporte.
3. Aplicar ediciones con `edit_file` cuidando la indentación y ejecutar nuevamente el test antes de llamar a
   `submit_patch()`.
