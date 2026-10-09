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

Límite conocido: el texto parcial de una petición cortada no se guarda (el arnés no usa streaming).
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
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
            latido: dict[str, Any] = {
                "hora": round(ahora, 3),
                "hora_utc": datetime.fromtimestamp(ahora, UTC).isoformat(timespec="seconds"),
                "sesion_s": round(ahora - self.t_sesion, 1),
                "etiqueta": self.estado["etiqueta"],
                "tarea": self.estado["tarea"],
                "peticiones": self.peticiones,
                "en_vuelo": en_vuelo,
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
        self.estado.update(etiqueta=etiqueta, tarea=instance_id, indice=indice)
        self.evento("tarea_inicio", indice=indice, peticiones_previas=self.peticiones)

    def fin_tarea(self, **campos: Any) -> None:
        """Fila con el motivo de fin de la tarea, se resuelva o no, y lo que quedó en vuelo."""
        with self._lock:
            pendientes = sorted(self.en_vuelo)
        self.evento("tarea_fin", peticiones=self.peticiones, en_vuelo=pendientes, **campos)
        self.estado.update(tarea=None, indice=None)

    def corte(self, por: str, **campos: Any) -> None:
        with self._lock:
            pendientes = sorted(self.en_vuelo)
        self.evento("corte", cortado_por=por, peticiones=self.peticiones, en_vuelo=pendientes, **campos)

    def archivos(self) -> list[Path]:
        """Archivos del registro que el notebook copia al zip de salida."""
        if not self.activo:
            return []
        rutas = (self.ruta_eventos, self.ruta_latido, self.ruta_servidor)
        return [p for p in rutas if p.exists()]

    def resumen(self) -> dict[str, Any]:
        return {
            "peticiones": self.peticiones,
            "motivos": dict(self.motivos),
            "en_vuelo": sorted(self.en_vuelo),
            "retrollamadas": dict(self.retrollamadas),
            "latidos": self.latidos,
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
        registro no termina en `cierre` murió desde fuera.
        """
        if not self.activo:
            return
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
) -> Registro:
    """Crea el registro e instala los seis enganches. Cada enganche se anota: instalado, o por qué no."""
    if parche_rich not in MODOS_RICH:
        raise ValueError(f"parche_rich debe ser uno de {MODOS_RICH}")
    registro = Registro(carpeta, nombre, servidor, activo=activo, latido_segundos=latido_segundos)
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
    instalar("retrollamadas de litellm", retrollamadas)
    instalar("motivo de fin del agente (Evaluator._run_agent_sandbox)", evaluador)
    instalar("diff al cierre (sandbox de agent_runner)", sandbox)
    instalar("logs por tarea (rich)", rich)
    instalar("log del servidor", lambda: f"origen {getattr(servidor, 'log_path', None)}")
    registro.arrancar_latido()
    registro.enganches["latido"] = f"cada {registro.latido_segundos} s"
    registro.evento("registro_instalado", nucleo=nucleo(), enganches=registro.enganches, pid=os.getpid())
    print("REGISTRO", nombre, "| nucleo", nucleo(), flush=True)
    for enganche, estado in registro.enganches.items():
        print("REGISTRO enganche", enganche, "->", estado, flush=True)
    return registro
