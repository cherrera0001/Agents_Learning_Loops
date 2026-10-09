"""Enganches de registro del notebook de la iteración 08 del experimento Kaggle (#160).

Este archivo se copia tal cual como una celda del notebook (`armar.py` de la iteración 08 lo incrusta y
comprueba que la celda es este texto, byte a byte). Por eso no importa nada del repositorio, no usa
`from __future__` y solo carga el arnés dentro de `instalar_registro`.

Deja en disco, sin depender de la consola, lo que hace falta para explicar un corte:

1. inicio y fin de cada petición al modelo, emparejados por número (`peticion_inicio` y `peticion_fin`);
2. el motivo de fin de cada petición (`stop`, `tool_calls`, `length`, `cancelada` o `error`) y el de cada
   sesión del agente (`agente_fin`), que el arnés descarta cuando el parche pasa las pruebas;
3. un latido periódico con el estado de la GPU, la salud del servidor, la petición en vuelo y el diff del
   árbol de la tarea en curso;
4. una copia del log entero del servidor del modelo, que el arnés borra al detenerlo;
5. el diff del árbol de la tarea al cierre de cada sesión del agente, haya entrega o no;
6. el parche que devuelve los logs por tarea bajo un núcleo Jupyter.

Cada evento es una línea JSON. El inicio de una petición se sincroniza a disco antes de llamar al modelo: si
la sesión muere desde fuera, ese inicio ya está en el archivo y le falta su fin. Ningún enganche puede
detener el arnés: un fallo del registro se cuenta y se anota, y la llamada original sigue.

El envoltorio de la llamada ve una cancelación (deja un fin con motivo `cancelada`); las retrollamadas de
litellm, no: ante una cancelación solo se dispara la de antes de la llamada. Se registran las dos vías para
que cada corrida lo vuelva a medir.

Parche de rich, modo `archivo`: fuerza `force_jupyter=False` solo en la consola del log por tarea. El modo
`global` (`rich.console._is_jupyter = lambda: False`) también devuelve los logs, pero cambia la consola que
pinta en el notebook y multiplica por más de cien el texto que la celda de tareas manda a la salida.

Dos guardias, para no descubrir al final de la sesión que el registro no registró: `exigir_enganches`
detiene el notebook antes de la primera tarea si un enganche exigido no quedó instalado, y
`comprobar_primera_tarea` lo detiene tras la primera si su log por tarea pesa 0 bytes, si no hay ninguna
petición respondida o si la tarea no dejó su `agente_fin` o su `diff_cierre`. Un enganche puede decir
«instalado» y no surtir efecto: por eso la segunda. Los enganches `log del servidor` y `latido` no pueden
quedar en FALLO, así que la primera guardia no los cubre.

Límite conocido: el texto parcial de una petición cortada no se guarda (el arnés no usa streaming).

Tope por tarea y mapa de hilos del núcleo (#164). En `ipykernel` 6.29.5 una escritura a stdout o stderr desde
un hilo recorre el mapa `_thread_to_parent` de `OutStream` sin guardia: si el mapa cierra un ciclo, el hilo
gira para siempre. Tres defensas, que no tocan al agente ni sus topes:

- `Registro.tarea` vacía ese mapa antes de cada tarea y anota en `tarea_inicio` cuántas entradas había y si
  cerraban un ciclo. Si no hay núcleo de Jupyter o el atributo no existe en esa versión, lo anota y sigue;
- `Registro.correr_con_tope` corre cada tarea en un hilo demonio y la espera como mucho el tope. Vale con
  cualquier versión de `ipykernel` y para cualquier causa del cuelgue;
- `Registro.tarea_colgada` vuelca la pila de todos los hilos, pide la cancelación de la tarea, vacía el mapa
  y espera un margen corto. Devuelve True solo si el hilo de la tarea terminó: entonces el notebook puede
  seguir con la tarea siguiente. Si el hilo sigue vivo, o es la segunda tarea colgada seguida, devuelve
  False y el notebook termina la sesión. Nunca corren dos tareas a la vez.
"""

import asyncio
import faulthandler
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONSULTA_GPU = (
    "nvidia-smi",
    "--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu",
    "--format=csv,noheader,nounits",
)
# La misma orden con que el arnés calcula el parche de una sesión sin entrega (agent_runner.py).
DIFF_AL_CIERRE = (
    "cd /workspace && git add -N . >/dev/null 2>&1; "
    "(git diff --binary _swegemma_baseline 2>/dev/null || git diff --binary HEAD)"
)
MODOS_RICH = ("archivo", "global", "ninguno")
ENGANCHE_NO_EXIGIDO = "retrollamadas de litellm"
CLASE_TAREA_COLGADA = "tarea_colgada"
PAQUETES_CON_VERSION = ("ipykernel", "jupyter_client", "nbclient", "papermill", "rich", "litellm")


def caracteres_de(x: Any) -> int:
    """Caracteres de texto de una estructura de mensajes, sin construir el texto unido."""
    if isinstance(x, str):
        return len(x)
    if isinstance(x, dict):
        return sum(caracteres_de(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return sum(caracteres_de(v) for v in x)
    if x is None or isinstance(x, (bool, int, float)):
        return 0
    volcar = getattr(x, "model_dump", None)
    if callable(volcar):
        return caracteres_de(volcar())
    return len(str(x))


def inicio_de_sesion() -> float:
    """Hora de arranque de este proceso según /proc (Linux); si no se puede leer, ahora."""
    try:
        with open("/proc/self/stat") as f:
            campos = f.read().rsplit(")", 1)[1].split()
        with open("/proc/stat") as f:
            btime = next(float(linea.split()[1]) for linea in f if linea.startswith("btime"))
        return btime + float(campos[19]) / os.sysconf("SC_CLK_TCK")
    except Exception:
        return time.time()


def archivos_de_un_diff(texto: str, tope: int = 50) -> list[str]:
    """Rutas que toca un diff de git, en orden y sin repetir."""
    rutas: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith("diff --git a/") and " b/" in linea:
            ruta = linea.split(" b/", 1)[1]
            if ruta not in rutas:
                rutas.append(ruta)
    return rutas[:tope]


class TareaColgada(RuntimeError):
    """La tarea no volvió dentro del tope por tarea. Su hilo sigue vivo: Python no puede matarlo."""

    def __init__(self, tope_segundos: float, segundos: float, hilo: Any = None, caja: Any = None) -> None:
        super().__init__(f"la tarea no volvió en {round(segundos, 1)} s (tope por tarea: {tope_segundos} s)")
        self.tope_segundos = tope_segundos
        self.segundos = segundos
        self.hilo = hilo
        self.caja = caja if caja is not None else {}


def nucleo_de_jupyter() -> Any:
    """El núcleo de Jupyter en que corre esta celda, o None si no hay IPython o no es un núcleo."""
    try:
        return getattr(get_ipython(), "kernel", None)  # type: ignore[name-defined]
    except NameError:
        return None


def versiones() -> dict[str, Any]:
    """Versión de Python y de los paquetes que deciden si el núcleo se parece al del laboratorio."""
    import importlib.metadata

    hallado: dict[str, Any] = {"python": sys.version.split()[0]}
    for paquete in PAQUETES_CON_VERSION:
        try:
            hallado[paquete] = importlib.metadata.version(paquete)
        except Exception:
            hallado[paquete] = None
    return hallado


def flujos_con_mapa() -> tuple[list[Any], str]:
    """Flujos de salida del núcleo que llevan el mapa de hilo a padre, y con qué texto se anota.

    Se mira `_stdout` y `_stderr` del núcleo y también `sys.stdout` y `sys.stderr`. En las versiones de
    `ipykernel` sin ese mapa la lista sale vacía: no es un fallo.
    """
    nucleo = nucleo_de_jupyter()
    if nucleo is None:
        return [], "sin núcleo de Jupyter"
    flujos: list[Any] = []
    for flujo in (getattr(nucleo, "_stdout", None), getattr(nucleo, "_stderr", None), sys.stdout, sys.stderr):
        mapa = getattr(flujo, "_thread_to_parent", None)
        if isinstance(mapa, dict) and all(flujo is not otro for otro in flujos):
            flujos.append(flujo)
    if not flujos:
        return [], f"este ipykernel ({versiones()['ipykernel']}) no tiene el mapa _thread_to_parent"
    return flujos, f"{len(flujos)} flujos con mapa (ipykernel {versiones()['ipykernel']})"


def hay_ciclo(mapa: dict[Any, Any]) -> bool:
    """True si recorrer el mapa desde alguna de sus claves no termina nunca."""
    copia = dict(mapa)
    for inicio in copia:
        vistos, actual = set(), inicio
        while actual in copia:
            if actual in vistos:
                return True
            vistos.add(actual)
            actual = copia[actual]
    return False


def mapa_de_hilos(vaciar: bool) -> dict[str, Any]:
    """Estado del mapa de hilo a padre del núcleo; con `vaciar`, además lo deja vacío. Nunca lanza.

    Devuelve `disponible`, `entradas` y `ciclo` (lo que había antes de vaciar) y `vaciado`.
    """
    try:
        flujos, detalle = flujos_con_mapa()
        if not flujos:
            return {"disponible": False, "motivo": detalle, "vaciado": False}
        entradas, ciclo = 0, False
        for flujo in flujos:
            mapa = flujo._thread_to_parent
            entradas += len(mapa)
            ciclo = hay_ciclo(mapa) or ciclo
            if vaciar:
                mapa.clear()
        return {"disponible": True, "entradas": entradas, "ciclo": ciclo, "vaciado": bool(vaciar)}
    except Exception as exc:
        return {"disponible": False, "motivo": type(exc).__name__ + ": " + str(exc)[:120], "vaciado": False}


def carga_del_sistema() -> dict[str, Any]:
    """Carga de la máquina, número de CPU e hilos vivos de este proceso. Lo que falte se anota como error."""
    carga: dict[str, Any] = {"cpus": os.cpu_count(), "hilos_vivos": threading.active_count()}
    try:
        carga["cpus_utilizables"] = len(
            os.sched_getaffinity(0)
        )  # afinidad: no existe en todas las plataformas
    except (AttributeError, OSError) as exc:
        carga["cpus_utilizables"] = {"error": type(exc).__name__}
    try:
        carga["carga"] = [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError) as exc:
        carga["carga"] = {"error": type(exc).__name__}
    return carga


def cpu_de_un_hilo(hilo: Any) -> float | None:
    """Segundos de CPU que lleva gastados un hilo vivo (Linux). None si no se puede leer."""
    try:
        return round(time.clock_gettime(time.pthread_getcpuclockid(hilo.ident)), 2)
    except Exception:
        return None


class Registro:
    """Escribe los eventos de una sesión del notebook y lleva la cuenta de las peticiones en vuelo."""

    def __init__(
        self,
        carpeta: Path,
        nombre: str,
        servidor: Any = None,
        *,
        activo: bool = True,
        latido_segundos: float = 30.0,
    ) -> None:
        self.carpeta = Path(carpeta)
        self.nombre = nombre
        self.servidor = servidor
        self.activo = activo
        self.latido_segundos = float(latido_segundos)
        self.ruta_eventos = self.carpeta / f"registro_{nombre}.jsonl"
        self.ruta_latido = self.carpeta / f"latido_{nombre}.jsonl"
        self.ruta_servidor = self.carpeta / f"servidor_log_{nombre}.txt"
        self.ruta_diff_en_curso = self.carpeta / f"diff_en_curso_{nombre}.diff"
        self.ruta_pila = self.carpeta / f"pila_tarea_colgada_{nombre}.txt"
        self.t_sesion = inicio_de_sesion()
        self.estado: dict[str, Any] = {"etiqueta": None, "tarea": None, "indice": None}
        self.en_vuelo: dict[int, dict[str, Any]] = {}
        self.espacio: Path | None = None
        self.peticiones = 0
        self.motivos: dict[str, int] = {}
        self.retrollamadas: dict[str, int] = {}
        self.enganches: dict[str, str] = {}
        self.errores = 0
        self.ultimo_error: str | None = None
        self.costo_segundos = 0.0
        self.costos: dict[str, list[float]] = {}
        self.latidos = 0
        self.parche_rich = "archivo"
        self.vistos: dict[str, int] = {}
        self.diffs_tomados = 0
        self.vaciar_mapa = True
        self.ultimo_evento: tuple[str, float] | None = None
        self.t_tarea: float | None = None
        self.hilo_de_tarea: threading.Thread | None = None
        self.con_tope: bool | None = None
        self.tareas_con_tope = 0
        self.colgadas = 0
        self.colgadas_seguidas = 0
        self.ciclos_vaciados = 0
        self.cerrado = False
        self._lock = threading.RLock()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    # -- escritura ---------------------------------------------------------------------------------

    def _anotar_error(self, exc: BaseException) -> None:
        self.errores += 1
        self.ultimo_error = type(exc).__name__ + ": " + str(exc)[:200]

    def _costo(self, parte: str, segundos: float) -> None:
        """Tiempo que el registro le quita al hilo que lo llama, por parte: [veces, segundos]."""
        self.costo_segundos += segundos
        cuenta = self.costos.setdefault(parte, [0, 0.0])
        cuenta[0] += 1
        cuenta[1] += segundos

    def _linea(self, ruta: Path, registro: dict[str, Any], sincronizar: bool = True) -> None:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
            f.flush()
            if sincronizar:
                os.fsync(f.fileno())

    def evento(self, tipo: str, **campos: Any) -> None:
        """Añade una línea al registro y la sincroniza a disco. Nunca lanza.

        El fin de una petición y las retrollamadas de litellm (`cb_*`) se escriben sin sincronizar: lo que
        no puede perderse es el inicio, y el siguiente evento sincronizado los lleva a disco con él.
        """
        if not self.activo:
            return
        t0 = time.perf_counter()
        try:
            ahora = time.time()
            with self._lock:
                self.ultimo_evento = (tipo, ahora)
                self._linea(
                    self.ruta_eventos,
                    {
                        "evento": tipo,
                        "hora": round(ahora, 3),
                        "hora_utc": datetime.fromtimestamp(ahora, UTC).isoformat(timespec="milliseconds"),
                        "sesion_s": round(ahora - self.t_sesion, 3),
                        "etiqueta": self.estado["etiqueta"],
                        "tarea": self.estado["tarea"],
                        **campos,
                    },
                    sincronizar=tipo != "peticion_fin" and not tipo.startswith("cb_"),
                )
                self.vistos[tipo] = self.vistos.get(tipo, 0) + 1
        except Exception as exc:
            self._anotar_error(exc)
        finally:
            self._costo(tipo, time.perf_counter() - t0)

    # -- peticiones al modelo (enganches 1 y 2) ----------------------------------------------------

    def inicio_peticion(self, modelo: Any, mensajes: Any, herramientas: Any, opciones: dict[str, Any]) -> int:
        t0 = time.perf_counter()
        with self._lock:
            self.peticiones += 1
            numero = self.peticiones
        try:
            datos = {
                "peticion": numero,
                "modelo": str(modelo),
                "n_mensajes": len(mensajes) if hasattr(mensajes, "__len__") else None,
                "caracteres_entrada": caracteres_de(mensajes),
                "con_herramientas": bool(herramientas),
                "stream": bool(opciones.get("stream")),
            }
        except Exception as exc:
            self._anotar_error(exc)
            datos = {"peticion": numero}
        with self._lock:
            self.en_vuelo[numero] = {**datos, "hora": round(time.time(), 3), "tarea": self.estado["tarea"]}
        self._costo("medir_entrada", time.perf_counter() - t0)
        self.evento("peticion_inicio", **datos)
        return numero

    def fin_peticion(self, numero: int, respuesta: Any = None, error: BaseException | None = None) -> None:
        t0 = time.perf_counter()
        with self._lock:
            inicio = self.en_vuelo.pop(numero, None)
        datos: dict[str, Any] = {"peticion": numero}
        if inicio is not None:
            datos["segundos"] = round(time.time() - inicio["hora"], 3)
        try:
            if error is not None:
                datos["motivo"] = "cancelada" if isinstance(error, asyncio.CancelledError) else "error"
                datos["error"] = type(error).__name__
                datos["detalle"] = str(error)[:300]
            else:
                eleccion = (getattr(respuesta, "choices", None) or [None])[0]
                motivo = getattr(eleccion, "finish_reason", None)
                if motivo is None and isinstance(eleccion, dict):
                    motivo = eleccion.get("finish_reason")
                datos["motivo"] = str(motivo) if motivo is not None else "sin_motivo"
                uso = getattr(respuesta, "usage", None)
                for campo in ("prompt_tokens", "completion_tokens"):
                    valor = getattr(uso, campo, None)
                    if valor is not None:
                        datos[campo] = valor
        except Exception as exc:
            self._anotar_error(exc)
            datos.setdefault("motivo", "sin_motivo")
        with self._lock:
            self.motivos[datos["motivo"]] = self.motivos.get(datos["motivo"], 0) + 1
        self._costo("leer_respuesta", time.perf_counter() - t0)
        self.evento("peticion_fin", **datos)

    def envolver_cliente(self, clase: Any) -> None:
        """Envuelve `LiteLLMClient.acompletion`: es la única ruta por la que el arnés llama al modelo."""
        original = getattr(clase.acompletion, "_registro_original", clase.acompletion)
        registro = self

        async def acompletion(cliente: Any, *args: Any, **kwargs: Any) -> Any:
            modelo = kwargs.get("model", args[0] if args else None)
            mensajes = kwargs.get("messages", args[1] if len(args) > 1 else None)
            herramientas = kwargs.get("tools", args[2] if len(args) > 2 else None)
            numero = registro.inicio_peticion(modelo, mensajes, herramientas, kwargs)
            try:
                respuesta = await original(cliente, *args, **kwargs)
            except BaseException as exc:  # incluye CancelledError: es lo que deja un tope de tiempo
                registro.fin_peticion(numero, error=exc)
                raise
            registro.fin_peticion(numero, respuesta=respuesta)
            return respuesta

        acompletion._registro_original = original  # type: ignore[attr-defined]
        clase.acompletion = acompletion

    def enganchar_retrollamadas(self, litellm: Any, base: type) -> None:
        """Segundo canal, para medir cuál ve una cancelación: las retrollamadas de litellm."""
        registro = self

        def anotar(tipo: str, kwargs: Any, canal: str) -> None:
            llamada = kwargs.get("litellm_call_id") if isinstance(kwargs, dict) else None
            with registro._lock:
                registro.retrollamadas[tipo] = registro.retrollamadas.get(tipo, 0) + 1
                en_curso = max(registro.en_vuelo) if registro.en_vuelo else None
            registro.evento(tipo, llamada=str(llamada), canal=canal, peticion_en_curso=en_curso)

        class _RetrollamadasDeRegistro(base):  # type: ignore[misc, valid-type]
            def log_pre_api_call(self, model: Any, messages: Any, kwargs: Any) -> None:
                anotar("cb_antes", kwargs, "sincrono")

            def log_success_event(
                self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
            ) -> None:
                anotar("cb_exito", kwargs, "sincrono")

            async def async_log_success_event(
                self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
            ) -> None:
                anotar("cb_exito", kwargs, "asincrono")

            def log_failure_event(
                self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
            ) -> None:
                anotar("cb_fallo", kwargs, "sincrono")

            async def async_log_failure_event(
                self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
            ) -> None:
                anotar("cb_fallo", kwargs, "asincrono")

        previas = [c for c in (litellm.callbacks or []) if type(c).__name__ != "_RetrollamadasDeRegistro"]
        litellm.callbacks = [*previas, _RetrollamadasDeRegistro()]

    # -- diff del árbol (enganche 5) ---------------------------------------------------------------

    def envolver_evaluador(self, clase: Any) -> None:
        """Envuelve `Evaluator._run_agent_sandbox`: anota por qué terminó la sesión del agente.

        El arnés descarta ese motivo cuando el parche pasa las pruebas: una tarea «resuelta» puede haber
        agotado un tope, y sin esta fila no queda en ningún archivo.
        """
        original = getattr(clase._run_agent_sandbox, "_registro_original", clase._run_agent_sandbox)
        registro = self

        async def _run_agent_sandbox(evaluador: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                resultado = await original(evaluador, *args, **kwargs)
            except BaseException as exc:
                registro.evento("agente_fin", error=type(exc).__name__ + ": " + str(exc)[:300], lanzo=True)
                raise
            try:
                contexto = kwargs.get("context")
                registro.evento(
                    "agente_fin",
                    error=None if resultado[1] is None else str(resultado[1])[:300],
                    parche_caracteres=len(resultado[0] or ""),
                    entrego=getattr(contexto, "patch_submitted", None),
                    llamadas_herramientas=getattr(contexto, "tool_calls_used", None),
                    llamadas_modelo=getattr(contexto, "llm_calls_used", None),
                )
            except Exception as exc:
                registro._anotar_error(exc)
            return resultado

        _run_agent_sandbox._registro_original = original  # type: ignore[attr-defined]
        clase._run_agent_sandbox = _run_agent_sandbox

    def envolver_sandbox(self, modulo: Any) -> None:
        """Envuelve el arranque y la parada del sandbox del agente en `swegemma.harness.agent_runner`.

        El arnés destruye el sandbox al final de cada sesión; el diff se toma justo antes, también cuando
        la sesión termina con error y el arnés no llega a calcular su parche.
        """
        arrancar = getattr(modulo.sandbox_start, "_registro_original", modulo.sandbox_start)
        parar = getattr(modulo.sandbox_stop, "_registro_original", modulo.sandbox_stop)
        registro = self

        async def sandbox_start(docker: Any) -> Any:
            sandbox_id = await arrancar(docker)
            try:
                entrada = (getattr(docker, "sandboxes", None) or {}).get(sandbox_id) or {}
                registro.espacio = Path(entrada["workspace"]) if entrada.get("workspace") else None
            except Exception as exc:
                registro._anotar_error(exc)
            return sandbox_id

        async def sandbox_stop(docker: Any, sandbox_id: Any) -> Any:
            try:
                await registro.diff_al_cierre(modulo.sandbox_exec, docker, sandbox_id)
            finally:
                registro.espacio = None
                resultado = await parar(docker, sandbox_id)  # la parada original va siempre
            return resultado

        sandbox_start._registro_original = arrancar  # type: ignore[attr-defined]
        sandbox_stop._registro_original = parar  # type: ignore[attr-defined]
        modulo.sandbox_start = sandbox_start
        modulo.sandbox_stop = sandbox_stop

    async def diff_al_cierre(self, ejecutar: Any, docker: Any, sandbox_id: Any) -> None:
        if not self.activo:
            return
        try:
            resultado = await ejecutar(docker, sandbox_id, DIFF_AL_CIERRE)
            texto = str(getattr(resultado, "stdout", "") or "")
            datos = texto.encode("utf-8", "replace")
            ruta = None
            if self.estado["etiqueta"] and self.estado["tarea"]:
                carpeta = self.carpeta / "results" / str(self.estado["etiqueta"]) / "diffs_cierre"
                carpeta.mkdir(parents=True, exist_ok=True)
                ruta = carpeta / (str(self.estado["tarea"]).replace("/", "_") + ".diff")
                ruta.write_bytes(datos)
            self.diffs_tomados += 1
            self.evento(
                "diff_cierre",
                bytes=len(datos),
                sha256=hashlib.sha256(datos).hexdigest(),
                archivos=archivos_de_un_diff(texto),
                codigo=getattr(resultado, "exit_code", None),
                guardado=ruta is not None,
            )
        except Exception as exc:
            self._anotar_error(exc)
            self.evento("diff_cierre", error=type(exc).__name__ + ": " + str(exc)[:200])

    def _diff_en_curso(self) -> dict[str, Any] | None:
        """Diff del árbol de la tarea en curso, leído desde fuera del agente y sin tocar el índice de git."""
        espacio = self.espacio
        if espacio is None or not espacio.exists():
            return None
        base = ["git", "--no-optional-locks", "-C", str(espacio)]
        salida = subprocess.run(
            [*base, "diff", "--binary", "_swegemma_baseline"], capture_output=True, timeout=20
        )
        if salida.returncode != 0:
            salida = subprocess.run([*base, "diff", "--binary", "HEAD"], capture_output=True, timeout=20)
        estado = subprocess.run([*base, "status", "--porcelain"], capture_output=True, timeout=20)
        temporal = self.ruta_diff_en_curso.with_suffix(".tmp")
        temporal.write_bytes(salida.stdout)
        os.replace(temporal, self.ruta_diff_en_curso)
        return {
            "tarea": self.estado["tarea"],
            "bytes": len(salida.stdout),
            "sha256": hashlib.sha256(salida.stdout).hexdigest(),
            "sin_seguimiento": sum(
                1 for x in estado.stdout.decode("utf-8", "replace").splitlines() if x[:2] == "??"
            ),
        }

    # -- latido y log del servidor (enganches 3 y 4) -----------------------------------------------

    def copiar_log_del_servidor(self) -> int | None:
        """Copia entera del log del servidor. Devuelve sus bytes, o None si no hay log que copiar."""
        origen = getattr(self.servidor, "log_path", None)
        if not origen or not os.path.exists(origen):
            return None
        temporal = self.ruta_servidor.with_suffix(".tmp")
        shutil.copyfile(origen, temporal)
        os.replace(temporal, self.ruta_servidor)
        return self.ruta_servidor.stat().st_size

    def _salud(self) -> Any:
        import urllib.request

        base = str(getattr(self.servidor, "base_url", "") or "").rstrip("/")
        if not base:
            return None
        base = base[:-3] if base.endswith("/v1") else base
        try:
            with urllib.request.urlopen(base + "/health", timeout=5) as r:
                return r.status == 200 or f"estado {r.status}"
        except Exception as exc:
            return type(exc).__name__ + ": " + str(exc)[:120]

    def _gpu(self) -> Any:
        try:
            salida = subprocess.run(CONSULTA_GPU, capture_output=True, text=True, timeout=10)
            if salida.returncode != 0:
                return {"error": f"nvidia-smi salió con {salida.returncode}"}
            return [
                [c.strip() for c in linea.split(",")] for linea in salida.stdout.splitlines() if linea.strip()
            ]
        except Exception as exc:
            return {"error": type(exc).__name__}

    def latir(self) -> None:
        """Un latido: GPU, salud y proceso del servidor, petición en vuelo, copia del log y diff en curso."""
        if not self.activo:
            return
        try:
            ahora = time.time()
            with self._lock:
                en_vuelo = [
                    {
                        "peticion": n,
                        "segundos_en_vuelo": round(ahora - p["hora"], 1),
                        "caracteres_entrada": p.get("caracteres_entrada"),
                    }
                    for n, p in sorted(self.en_vuelo.items())
                ]
            proceso = getattr(self.servidor, "process", None)
            ultimo, hilo, t_tarea = self.ultimo_evento, self.hilo_de_tarea, self.t_tarea
            latido: dict[str, Any] = {
                "hora": round(ahora, 3),
                "hora_utc": datetime.fromtimestamp(ahora, UTC).isoformat(timespec="seconds"),
                "sesion_s": round(ahora - self.t_sesion, 1),
                "etiqueta": self.estado["etiqueta"],
                "tarea": self.estado["tarea"],
                "peticiones": self.peticiones,
                "en_vuelo": en_vuelo,
                # Lo que distingue una tarea que gira o está bloqueada de una que avanza (#164)
                "ultimo_evento": None if ultimo is None else ultimo[0],
                "segundos_sin_eventos": None if ultimo is None else round(ahora - ultimo[1], 1),
                "tarea_segundos": None if t_tarea is None else round(ahora - t_tarea, 1),
                "hilo_de_tarea": None
                if hilo is None
                else {"vivo": hilo.is_alive(), "cpu_s": cpu_de_un_hilo(hilo)},
                **carga_del_sistema(),
                "gpu": self._gpu(),
                "servidor_sano": self._salud(),
                "servidor_codigo_de_salida": proceso.poll() if proceso is not None else None,
            }
            for clave, medir in (
                ("servidor_log_bytes", self.copiar_log_del_servidor),
                ("diff_en_curso", self._diff_en_curso),
            ):
                try:
                    latido[clave] = medir()
                except Exception as exc:
                    latido[clave] = {"error": type(exc).__name__ + ": " + str(exc)[:120]}
            with self._lock:
                self._linea(self.ruta_latido, latido)
                self.latidos += 1
        except Exception as exc:
            self._anotar_error(exc)

    def _bucle_del_latido(self) -> None:
        self.latir()
        while not self._parar.wait(self.latido_segundos):
            self.latir()

    def arrancar_latido(self) -> None:
        if not self.activo or self._hilo is not None:
            return
        self._hilo = threading.Thread(target=self._bucle_del_latido, name="latido-registro", daemon=True)
        self._hilo.start()

    # -- lo que llama el notebook ------------------------------------------------------------------

    def tarea(self, etiqueta: str, instance_id: str, indice: int) -> None:
        """Inicio de una tarea. Antes vacía el mapa de hilos del núcleo: quita la causa probable del giro."""
        self.estado.update(etiqueta=etiqueta, tarea=instance_id, indice=indice)
        mapa = (
            mapa_de_hilos(vaciar=True)
            if self.vaciar_mapa
            else {**mapa_de_hilos(vaciar=False), "motivo": "vaciado desactivado"}
        )
        if mapa.get("ciclo") and mapa.get("vaciado"):
            self.ciclos_vaciados += 1
        self.t_tarea, self.con_tope = time.time(), False
        self.evento("tarea_inicio", indice=indice, peticiones_previas=self.peticiones, mapa_de_hilos=mapa)

    def fin_tarea(self, **campos: Any) -> None:
        """Fila con el motivo de fin de la tarea, se resuelva o no, y lo que quedó en vuelo."""
        with self._lock:
            pendientes = sorted(self.en_vuelo)
        # Una tarea cortada por el tope por tarea no es una tarea «no resuelta»: es un par que falta al
        # comparar dos pasadas. Se marca con un campo propio para poder excluirla.
        colgada = campos.get("clase") == CLASE_TAREA_COLGADA
        self.evento(
            "tarea_fin",
            peticiones=self.peticiones,
            en_vuelo=pendientes,
            con_tope=self.con_tope,
            par_faltante=colgada,
            **campos,
        )
        if not colgada:
            self.colgadas_seguidas = 0
        self.estado.update(tarea=None, indice=None)
        self.t_tarea, self.hilo_de_tarea = None, None

    # -- tope por tarea (#164) ---------------------------------------------------------------------

    def correr_con_tope(self, fabrica: Any, tope_segundos: float) -> Any:
        """Corre la corrutina de `fabrica()` en un hilo demonio y la espera como mucho `tope_segundos`.

        Sustituye al `with ThreadPoolExecutor` del notebook, que esperaba sin tope y, al salir, volvía a
        esperar al hilo. Si la tarea no vuelve lanza `TareaColgada` con el hilo, que sigue vivo. No depende
        de que el registro esté activo ni de la versión de `ipykernel`.
        """
        caja: dict[str, Any] = {}

        async def principal() -> Any:
            caja["bucle"], caja["tarea"] = asyncio.get_running_loop(), asyncio.current_task()
            return await fabrica()

        def cuerpo() -> None:
            try:
                caja["valor"] = asyncio.run(principal())
            except BaseException as exc:  # se entrega a quien espera, como hace un Future
                caja["error"] = exc

        hilo = threading.Thread(target=cuerpo, name="tarea-del-notebook", daemon=True)
        self.hilo_de_tarea, self.con_tope = hilo, True
        self.tareas_con_tope += 1
        t0 = time.time()
        hilo.start()
        hilo.join(tope_segundos)
        if hilo.is_alive():
            raise TareaColgada(tope_segundos, time.time() - t0, hilo, caja)
        if "error" in caja:
            raise caja["error"]
        return caja["valor"]

    def volcar_pila(self) -> dict[str, Any]:
        """Pila de todos los hilos, con `faulthandler`, en un archivo de la salida. Nunca lanza."""
        if not self.activo:
            return {}
        try:
            with open(self.ruta_pila, "a", encoding="utf-8") as f:
                f.write(
                    f"=== {datetime.now(UTC).isoformat(timespec='seconds')} tarea {self.estado['tarea']} "
                    f"hilo de la tarea {getattr(self.hilo_de_tarea, 'ident', None)}\n"
                )
                for hilo in threading.enumerate():
                    f.write(
                        f"hilo {hilo.ident} 0x{hilo.ident or 0:016x} {hilo.name} demonio={hilo.daemon} "
                        f"cpu_s={cpu_de_un_hilo(hilo)}\n"
                    )
                f.flush()
                faulthandler.dump_traceback(file=f, all_threads=True)
                f.flush()
                os.fsync(f.fileno())
            return {"pila": self.ruta_pila.name, "pila_bytes": self.ruta_pila.stat().st_size}
        except Exception as exc:
            self._anotar_error(exc)
            return {"pila": None, "pila_error": type(exc).__name__ + ": " + str(exc)[:120]}

    def tarea_colgada(self, colgada: TareaColgada, margen_segundos: float, **campos: Any) -> bool:
        """El notebook dejó de esperar la tarea en curso. Devuelve True si puede seguir con la siguiente.

        Vuelca la pila, pide la cancelación de la tarea, vacía el mapa de hilos (si el hilo giraba en él,
        eso lo suelta) y espera `margen_segundos` a que el hilo termine. Solo se sigue si el hilo terminó
        y no es la segunda tarea colgada seguida: con el hilo vivo habría dos tareas a la vez sobre el
        mismo servidor y el mismo registro. Nunca lanza.
        """
        hilo, caja = colgada.hilo, colgada.caja
        try:
            self.colgadas += 1
            self.colgadas_seguidas += 1
            pila = self.volcar_pila()
            cpu_antes = cpu_de_un_hilo(hilo)
            antes = mapa_de_hilos(vaciar=False)
            try:
                caja["bucle"].call_soon_threadsafe(caja["tarea"].cancel)
                cancelacion = "pedida"
            except Exception as exc:
                cancelacion = "no se pudo pedir: " + type(exc).__name__
            t0 = time.time()
            mapa_de_hilos(vaciar=True)
            if hilo is not None:
                hilo.join(max(0.0, float(margen_segundos)))
            vivo = hilo is None or hilo.is_alive()
            sigue = not vivo and self.colgadas_seguidas < 2
            self.evento(
                "tarea_colgada",
                tope_s=colgada.tope_segundos,
                segundos=round(colgada.segundos, 1),
                **pila,
                mapa_de_hilos=antes,
                cancelacion=cancelacion,
                margen_s=margen_segundos,
                hilo_vivo=vivo,
                segundos_hasta_terminar=None if vivo else round(time.time() - t0, 2),
                cpu_del_hilo_s=[cpu_antes, cpu_de_un_hilo(hilo) if vivo else None],
                colgadas_seguidas=self.colgadas_seguidas,
                sigue=sigue,
                **carga_del_sistema(),
                **campos,
            )
            return sigue
        except Exception as exc:
            self._anotar_error(exc)
            return False

    def corte(self, por: str, **campos: Any) -> None:
        with self._lock:
            pendientes = sorted(self.en_vuelo)
        self.evento("corte", cortado_por=por, peticiones=self.peticiones, en_vuelo=pendientes, **campos)

    def enganches_que_faltan(self) -> list[str]:
        """Enganches exigidos que no quedaron instalados (las retrollamadas solo sirven para comparar)."""
        if not self.activo:
            return []
        return [
            nombre
            for nombre, estado in self.enganches.items()
            if estado.startswith("FALLO") and nombre != ENGANCHE_NO_EXIGIDO
        ]

    def exigir_enganches(self) -> None:
        """Guardia previa a la primera tarea: sin registro completo no se gasta cuota."""
        faltan = self.enganches_que_faltan()
        if faltan:
            self.evento("guardia", cuando="antes de la primera tarea", problemas=faltan)
            raise RuntimeError(
                "GUARDIA registro: no quedó instalado "
                + "; ".join(f"{n} ({self.enganches[n]})" for n in faltan)
            )

    def comprobar_primera_tarea(self, ruta_log: Path) -> None:
        """Guardia tras la primera tarea: mira que cada enganche dejó lo suyo.

        Su log por tarea pesa más de 0 bytes, hay una petición respondida, y la tarea dejó su `agente_fin` y
        su `diff_cierre`. Un enganche puede decir «instalado» y no surtir efecto (el arnés crea la consola,
        llama al modelo o destruye el sandbox por otra ruta): solo se ve mirando lo que la primera tarea dejó.
        """
        if not self.activo:
            return
        problemas = []
        if self.parche_rich != "ninguno":
            ruta = Path(ruta_log)
            if not ruta.exists():
                problemas.append(f"no existe el log por tarea {ruta.name}")
            elif ruta.stat().st_size == 0:
                problemas.append(f"el log por tarea {ruta.name} pesa 0 bytes")
        respondidas = sum(v for k, v in self.motivos.items() if k not in ("cancelada", "error"))
        if respondidas == 0:
            sin_respuesta = sum(v for k, v in self.motivos.items() if k in ("cancelada", "error"))
            problemas.append(
                f"el registro no tiene ninguna petición respondida ({self.peticiones} iniciadas, "
                f"{sin_respuesta} con error o canceladas): o el enganche de peticiones no surte efecto, o el "
                "servidor no respondió"
            )
        if self.vistos.get("agente_fin", 0) == 0:
            problemas.append("la primera tarea no dejó su agente_fin (motivo de fin del agente)")
        if self.diffs_tomados == 0:
            problemas.append("la primera tarea no dejó su diff_cierre (diff del árbol al cierre)")
        if problemas:
            self.evento("guardia", cuando="tras la primera tarea", problemas=problemas)
            raise RuntimeError("GUARDIA registro: " + "; ".join(problemas))

    def archivos(self) -> list[Path]:
        """Archivos del registro que el notebook copia al zip de salida."""
        if not self.activo:
            return []
        rutas = (self.ruta_eventos, self.ruta_latido, self.ruta_servidor, self.ruta_pila)
        return [p for p in rutas if p.exists()]

    def resumen(self) -> dict[str, Any]:
        return {
            "peticiones": self.peticiones,
            "motivos": dict(self.motivos),
            "en_vuelo": sorted(self.en_vuelo),
            "retrollamadas": dict(self.retrollamadas),
            "latidos": self.latidos,
            "tareas_colgadas": self.colgadas,
            "ciclos_vaciados_del_mapa_de_hilos": self.ciclos_vaciados,
            "errores_del_registro": self.errores,
            "ultimo_error": self.ultimo_error,
            "costo_del_registro_s": round(self.costo_segundos, 4),
            "costo_por_parte (veces, ms de media)": {
                k: [int(v[0]), round(1000 * v[1] / v[0], 3)] for k, v in sorted(self.costos.items())
            },
        }

    def cerrar(self) -> None:
        """Último latido (con la copia final del log del servidor) y evento de cierre.

        Hay que llamarlo antes de detener el servidor: el arnés borra su log al detenerlo. Una sesión cuyo
        registro no termina en `cierre` murió desde fuera. Una segunda llamada no hace nada: el notebook
        cierra en la celda de tareas cuando termina la sesión por una tarea colgada, y otra vez al final.
        """
        if not self.activo or self.cerrado:
            return
        self.cerrado = True
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=60)
        self.latir()
        self.evento("cierre", **self.resumen())


def instalar_registro(
    carpeta: Path,
    nombre: str,
    servidor: Any = None,
    *,
    activo: bool = True,
    parche_rich: str = "archivo",
    latido_segundos: float = 30.0,
    vaciar_mapa: bool = True,
) -> Registro:
    """Crea el registro e instala los seis enganches. Cada enganche se anota: instalado, o por qué no.

    `vaciar_mapa=False` solo sirve al ensayo: deja el mapa de hilos del núcleo como está antes de cada tarea.
    """
    if parche_rich not in MODOS_RICH:
        raise ValueError(f"parche_rich debe ser uno de {MODOS_RICH}")
    registro = Registro(carpeta, nombre, servidor, activo=activo, latido_segundos=latido_segundos)
    registro.parche_rich = parche_rich
    registro.vaciar_mapa = vaciar_mapa
    if not activo:
        print("REGISTRO", nombre, "inactivo: no se instala ningún enganche", flush=True)
        return registro

    def instalar(enganche: str, accion: Any) -> None:
        try:
            detalle = accion()
            registro.enganches[enganche] = "instalado" if detalle is None else str(detalle)
        except Exception as exc:
            registro.enganches[enganche] = "FALLO " + type(exc).__name__ + ": " + str(exc)[:200]

    def nucleo() -> str:
        try:
            return type(get_ipython()).__name__  # type: ignore[name-defined]
        except NameError:
            return "sin IPython"

    def cliente() -> None:
        from google.adk.models.lite_llm import LiteLLMClient

        registro.envolver_cliente(LiteLLMClient)

    def retrollamadas() -> None:
        import litellm
        from litellm.integrations.custom_logger import CustomLogger

        registro.enganchar_retrollamadas(litellm, CustomLogger)

    def sandbox() -> None:
        from swegemma.harness import agent_runner

        registro.envolver_sandbox(agent_runner)

    def evaluador() -> None:
        from swegemma.evaluate import Evaluator

        registro.envolver_evaluador(Evaluator)

    def rich() -> str:
        import rich.console

        antes = bool(rich.console._is_jupyter())
        if parche_rich == "global":
            rich.console._is_jupyter = lambda: False
        elif parche_rich == "archivo":
            # Solo la consola del log por tarea: el arnés la crea en agent_runner con este nombre. La
            # consola que pinta en el notebook sigue detectando Jupyter, como en las iteraciones previas.
            from swegemma.harness import agent_runner

            consola = getattr(agent_runner.Console, "_registro_original", agent_runner.Console)

            def consola_de_archivo(*args: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("force_jupyter", False)
                return consola(*args, **kwargs)

            consola_de_archivo._registro_original = consola  # type: ignore[attr-defined]
            agent_runner.Console = consola_de_archivo
        return (
            f"modo {parche_rich}; rich detectaba Jupyter: {antes}; ahora: {bool(rich.console._is_jupyter())}"
        )

    instalar("peticiones (envoltorio de LiteLLMClient.acompletion)", cliente)
    instalar(ENGANCHE_NO_EXIGIDO, retrollamadas)
    instalar("motivo de fin del agente (Evaluator._run_agent_sandbox)", evaluador)
    instalar("diff al cierre (sandbox de agent_runner)", sandbox)
    instalar("logs por tarea (rich)", rich)
    instalar("log del servidor", lambda: f"origen {getattr(servidor, 'log_path', None)}")
    registro.arrancar_latido()
    registro.enganches["latido"] = f"cada {registro.latido_segundos} s"
    # No es un enganche exigido: donde el mapa no existe no hay nada que vaciar, y el tope por tarea sigue.
    estado_del_mapa = mapa_de_hilos(vaciar=False)
    registro.enganches["mapa de hilos del núcleo"] = (
        ("se vacía antes de cada tarea" if vaciar_mapa else "no se vacía (desactivado)")
        if estado_del_mapa["disponible"]
        else "no disponible: " + str(estado_del_mapa.get("motivo"))
    )
    registro.evento(
        "registro_instalado",
        nucleo=nucleo(),
        enganches=registro.enganches,
        pid=os.getpid(),
        versiones=versiones(),
        mapa_de_hilos=estado_del_mapa,
        **carga_del_sistema(),
    )
    print("REGISTRO", nombre, "| nucleo", nucleo(), flush=True)
    # Lo que hay que saber de la plataforma antes de la primera tarea: versiones, mapa y carga.
    print("REGISTRO versiones", versiones(), flush=True)
    print("REGISTRO mapa de hilos", estado_del_mapa, "| maquina", carga_del_sistema(), flush=True)
    for enganche, estado in registro.enganches.items():
        print("REGISTRO enganche", enganche, "->", estado, flush=True)
    return registro
