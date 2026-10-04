"""Sesiones de notebooks en Kaggle: listar las que están activas o en cola y cancelar una.

Una versión en cola espera horas y, si su notebook está mal, falla en segundos al arrancar. Cancelarla a
tiempo evita gastar la espera. La API pública cancela, pero no dice qué sesiones hay:

- **Cancelar** se hace con el token: ``CancelKernelSession`` con el identificador de la sesión.
- **Listar** exige la sesión web del dueño: el identificador (``kernelRunId``) solo lo entrega la página.
  El dueño abre Edge con ``--remote-debugging-port`` y un perfil aparte, inicia sesión en Kaggle, y este
  guion se conecta a ese Edge. El inicio de sesión no se hace en un navegador automatizado: Google lo rechaza.

Uso:
    msedge --remote-debugging-port=9333 --user-data-dir=<perfil aparte> https://www.kaggle.com/account/login
    python -m scripts.kaggle_sesiones listar --usuario <usuario> --notebook <slug> [--puerto 9333]
    python -m scripts.kaggle_sesiones cancelar --sesion <kernelRunId> --usuario <usuario> --notebook <slug>

``listar`` necesita el paquete ``playwright``:
``uv run --with playwright python -m scripts.kaggle_sesiones listar …``.
``cancelar`` lee el token de ``KAGGLE_API_TOKEN`` y no lo imprime.

Salida: 0 si se hizo, 2 si la entrada es inválida o falta algo, 3 si Kaggle rechazó la operación.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

RPC = "https://api.kaggle.com/v1/kernels.KernelsApiService"
API = "https://www.kaggle.com/api/v1"
TOPE_S = 60

EXIT_OK = 0
EXIT_ENTRADA = 2
EXIT_RECHAZADA = 3


class SesionesError(RuntimeError):
    """Entrada inválida, falta de token o de sesión web, o rechazo de Kaggle."""


def resumir_sesiones(respuesta: dict[str, Any]) -> dict[str, Any]:
    """Lo útil de ``ListKernelSessions``: cada sesión con su identificador, y los límites de la cuenta."""
    sesiones = [
        {
            "sesion": s.get("kernelRunId"),
            "notebook": s.get("title"),
            "version": s.get("versionNumber"),
            "tipo": s.get("type"),
            "acelerador": s.get("accelerator"),
            "creada": s.get("dateCreated"),
        }
        for s in respuesta.get("sessions") or []
    ]
    return {"total": len(sesiones), "sesiones": sesiones, "limites": respuesta.get("quotaLimits") or {}}


def horas(duracion: object) -> float | None:
    """Horas de una duración de Kaggle con la forma ``"6809.76s"``; ``None`` si no tiene esa forma."""
    texto = str(duracion or "")
    if not texto.endswith("s"):
        return None
    try:
        return round(float(texto[:-1]) / 3600, 2)
    except ValueError:
        return None


def resumir_cuota(respuesta: dict[str, Any]) -> dict[str, Any]:
    gpu = respuesta.get("gpuQuota") or {}
    return {
        "gpu_horas_usadas": horas(gpu.get("timeUsed")),
        "gpu_horas_totales": horas(gpu.get("totalTimeAllowed")),
        "gpu_horas_reservadas": horas(gpu.get("timeReserved")),
        "reinicio": respuesta.get("quotaRefreshTime"),
    }


def resumir_versiones(respuesta: dict[str, Any]) -> list[dict[str, Any]]:
    """Cada versión del notebook con el identificador y el estado de su corrida."""
    out = []
    for item in respuesta.get("items") or []:
        corrida = item.get("run") or {}
        info = corrida.get("runInfo") or {}
        out.append(
            {
                "version": (item.get("version") or {}).get("versionNumber"),
                "sesion": corrida.get("id"),
                "estado": corrida.get("status") or "EN_COLA_O_CORRIENDO",
                "creada": corrida.get("dateCreated"),
                "evaluada": corrida.get("dateEvaluated"),
                "segundos_de_ejecucion": info.get("runTimeSeconds"),
                "codigo_de_salida": info.get("exitCode"),
            }
        )
    return out


def _token() -> str:
    token = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not token:
        raise SesionesError("Falta la variable KAGGLE_API_TOKEN.")
    return token


def _pedir(url: str, token: str, cuerpo: dict[str, Any] | None = None) -> tuple[int, str]:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    cabeceras = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    peticion = urllib.request.Request(
        url, data=datos, headers=cabeceras, method="GET" if datos is None else "POST"
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TOPE_S) as resp:
            return int(resp.status), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SesionesError(f"Sin respuesta de Kaggle: {type(exc).__name__}") from None


def estado(usuario: str, notebook: str, token: str) -> str:
    consulta = f"userName={urllib.parse.quote(usuario)}&kernelSlug={urllib.parse.quote(notebook)}"
    codigo, texto = _pedir(f"{API}/kernels/status?{consulta}", token)
    if codigo != 200:
        raise SesionesError(f"Kaggle respondió {codigo} al pedir el estado.")
    return str(json.loads(texto).get("status"))


def cancelar(sesion: int, token: str) -> None:
    """Cancela la sesión. Con un identificador ajeno o inexistente Kaggle responde 403."""
    codigo, texto = _pedir(f"{RPC}/CancelKernelSession", token, {"kernelSessionId": sesion})
    if codigo == 403:
        raise SesionesError("Kaggle negó el permiso: ese identificador no es de una sesión de esta cuenta.")
    if codigo != 200:
        raise SesionesError(f"Kaggle respondió {codigo} a la cancelación.")
    error = json.loads(texto or "{}").get("errorMessage")
    if error:
        raise SesionesError(f"Kaggle no canceló la sesión: {str(error)[:200]}")


def leer_con_sesion_web(usuario: str, notebook: str, puerto: int) -> dict[str, Any]:
    """Sesiones, cuota y versiones leídas desde un Edge en el que el dueño ya inició sesión."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SesionesError("Falta el paquete playwright: use «uv run --with playwright …».") from None
    with sync_playwright() as p:
        try:
            navegador = p.chromium.connect_over_cdp(f"http://127.0.0.1:{puerto}")
        except Exception:
            raise SesionesError(f"No hay un Edge con depuración en el puerto {puerto}.") from None
        contexto = navegador.contexts[0]
        pagina = contexto.new_page()
        try:
            pagina.goto(f"https://www.kaggle.com/code/{usuario}/{notebook}", wait_until="domcontentloaded")
            destino = pagina.evaluate("fetch('/me', {redirect: 'follow'}).then(r => r.url).catch(() => '')")
            if not str(destino).rstrip("/").lower().endswith("/" + usuario.lower()):
                raise SesionesError(f"El Edge del puerto {puerto} no tiene iniciada la sesión de {usuario}.")
            galletas = contexto.cookies("https://www.kaggle.com")
            xsrf = next((c["value"] for c in galletas if c["name"] == "XSRF-TOKEN"), "")
            guion = """async ([metodo, cuerpo, xsrf]) => {
                const cabeceras = {'content-type': 'application/json', 'x-xsrf-token': xsrf};
                const r = await fetch('/api/i/kernels.' + metodo,
                    {method: 'POST', headers: cabeceras, body: JSON.stringify(cuerpo)});
                return r.ok ? await r.json() : {};
            }"""
            quien = {"authorUserName": usuario, "kernelSlug": notebook}
            sesiones = pagina.evaluate(guion, ["KernelsService/ListKernelSessions", quien, xsrf])
            cuota = pagina.evaluate(guion, ["KernelsService/GetAcceleratorQuotaStatistics", {}, xsrf])
            vista = pagina.evaluate(guion, ["LegacyKernelsService/GetKernelViewModel", quien, xsrf])
            identificador = (vista.get("kernel") or {}).get("id")
            versiones = (
                pagina.evaluate(
                    guion, ["KernelsService/ListKernelVersions", {"kernelId": identificador}, xsrf]
                )
                if identificador
                else {}
            )
        finally:
            pagina.close()
    return {
        **resumir_sesiones(sesiones),
        "cuota": resumir_cuota(cuota),
        "versiones_del_notebook": resumir_versiones(versiones),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kaggle_sesiones", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)
    for nombre in ("listar", "cancelar"):
        s = sub.add_parser(nombre)
        s.add_argument("--usuario", required=True)
        s.add_argument("--notebook", required=True)
        if nombre == "listar":
            s.add_argument("--puerto", type=int, default=9333)
        else:
            s.add_argument("--sesion", type=int, required=True, help="kernelRunId que entrega «listar»")
    args = p.parse_args(argv)
    try:
        if args.comando == "listar":
            print(
                json.dumps(
                    leer_con_sesion_web(args.usuario, args.notebook, args.puerto),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return EXIT_OK
        if args.sesion <= 0:
            raise SesionesError("--sesion debe ser un identificador positivo.")
        token = _token()
    except SesionesError as exc:
        print(f"ENTRADA INVÁLIDA: {exc}", file=sys.stderr)
        return EXIT_ENTRADA
    try:
        cancelar(args.sesion, token)
        time.sleep(5)
        ahora = estado(args.usuario, args.notebook, token)
    except SesionesError as exc:
        print(f"KAGGLE RECHAZÓ LA OPERACIÓN: {exc}", file=sys.stderr)
        return EXIT_RECHAZADA
    print(json.dumps({"sesion_cancelada": args.sesion, "estado_del_notebook": ahora}, ensure_ascii=False))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
