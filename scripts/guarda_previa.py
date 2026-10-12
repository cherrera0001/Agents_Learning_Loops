"""Guardas previas a una orden de Bash (gancho ``PreToolUse`` de Claude Code, issue #186).

Dos guardas que el texto no logró hacer cumplir:

1. **Heredoc.** Rechaza una orden con un heredoc que alimenta un intérprete (``python -``, ``node``,
   ``bash``...), que escribe un archivo fuente (``cat > x.py <<EOF``) o cuyo cuerpo pasa de
   ``MAX_LINEAS_HEREDOC`` líneas. En Git Bash sobre Windows esos heredocs rompen las secuencias de
   escape o el cierre de comillas (11 pasos fallidos en ``learning/episodes/``).
2. **Cuenta de GitHub.** Rechaza una orden ``gh`` de escritura o un ``git push`` cuando el directorio de
   trabajo es este repositorio y la cuenta efectiva no es ``cherrera0001``.

Contrato del gancho: lee por stdin el JSON de Claude Code (``tool_name``, ``tool_input.command``, ``cwd``).
Para rechazar sale con 2 y escribe el motivo por stderr (forma documentada; ``exit 0`` con
``permissionDecision: deny`` es la otra, y no hace falta). Ante la duda deja pasar: un falso rechazo cuesta
más que un fallo que se escapa. Si el propio guion falla o pasa de ``TOPE_SEGUNDOS`` deja pasar la orden y
lo dice (stderr y ``systemMessage``). Nunca imprime ni guarda un token ni la orden entera.

Cada rechazo, y cada vez que deja pasar por duda o por fallo, suma una línea al registro local
``.claude/guarda_previa.jsonl`` (ignorado por git). Se lee con::

    python -m scripts.guarda_previa --contar

Solo biblioteca estándar. Solo cubre Claude Code: Codex y otros agentes no leen este gancho.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

CUENTA = "cherrera0001"
REPOSITORIO = "cherrera0001/agents_learning_loops"
# Un heredoc de texto plano más largo que esto se rechaza. Los mensajes de commit escritos a mano
# rara vez pasan de 20 líneas (29 de 152 cuerpos del historial pasan de 20, casi todos fusiones
# automáticas); 60 deja pasar un mensaje o un archivo de datos razonable y frena los cuerpos enteros de
# issue o de parche, que son los que fallaron por largo.
MAX_LINEAS_HEREDOC = 60
# Tope total del guion. El de ``.claude/settings.json`` es mayor (10 s) para que mande este.
TOPE_SEGUNDOS = 6.0
TOPE_SUBPROCESO = 2.0

INTERPRETES = (
    "python",
    "python3",
    "py",
    "node",
    "nodejs",
    "deno",
    "bun",
    "bash",
    "sh",
    "zsh",
    "dash",
    "pwsh",
    "powershell",
    "perl",
    "ruby",
    "php",
)
EXTENSIONES_FUENTE = (
    "py",
    "pyi",
    "js",
    "mjs",
    "cjs",
    "jsx",
    "ts",
    "tsx",
    "sh",
    "bash",
    "ps1",
    "bat",
    "cmd",
    "rb",
    "pl",
    "php",
    "go",
    "rs",
    "java",
    "c",
    "cc",
    "cpp",
    "h",
)
MENSAJE_HEREDOC = (
    "RECHAZADA por la guarda previa (#186): {motivo}. En Git Bash sobre Windows un heredoc así rompe las "
    "secuencias de escape (\\n, \\\\) o el cierre de comillas. En su lugar: escribe el archivo con la "
    "herramienta de edición (Write o Edit) y ejecútalo con una orden corta ({ejemplo}). Si la orden era "
    "legítima, reduce el heredoc o pásalo a un archivo; el rechazo queda contado en "
    ".claude/guarda_previa.jsonl."
)
MENSAJE_CUENTA = (
    "RECHAZADA por la guarda previa (#186): {motivo}. Esta escritura debe salir con la cuenta "
    f"{CUENTA}. Fija la cuenta en la propia orden, sin `gh auth switch`: "
    f'GH_TOKEN="$(gh auth token --user {CUENTA})" gh ... (y para git push: '
    f"git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push ...). "
    "Las lecturas no se frenan."
)

_OPERADOR_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([A-Za-z_][\w.-]*))")
_ASIGNACION = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.DOTALL)
_REDIRECCION_FUENTE = re.compile(
    r"(?:>>?|\btee(?:\s+-a)?)\s*['\"]?[^\s'\"|;&<>]*\.(?:" + "|".join(EXTENSIONES_FUENTE) + r")\b",
    re.IGNORECASE,
)
_SECRETO = re.compile(r"((?:GH|GITHUB)_TOKEN\s*=\s*)\S+|\bgh[pousr]_[A-Za-z0-9_]{10,}|\bgithub_pat_\w+")


class Heredoc:
    """Un heredoc encontrado: la línea del operador, su delimitador y su cuerpo."""

    def __init__(self, linea_operador: str, delimitador: str, cuerpo: list[str]) -> None:
        self.linea_operador = linea_operador
        self.delimitador = delimitador
        self.cuerpo = cuerpo


def encontrar_heredocs(orden: str) -> tuple[list[Heredoc], str]:
    """Heredocs reales de la orden y la orden sin sus cuerpos.

    Un ``<<`` es heredoc solo si tiene un delimitador y, en alguna línea posterior, una línea que sea
    exactamente ese delimitador (o la orden termina). ``1 << 3`` en ``python -c`` o dentro de una
    cadena de una sola línea no cumple y no se cuenta.
    """
    lineas = orden.replace("\r\n", "\n").split("\n")
    encontrados: list[Heredoc] = []
    resto: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        resto.append(linea)
        pendientes: list[tuple[bool, str, bool]] = []
        for m in _OPERADOR_HEREDOC.finditer(linea):
            citado = bool(m.group(2) or m.group(3))
            pendientes.append((m.group(1) == "-", m.group(2) or m.group(3) or m.group(4), citado))
        i += 1
        for quita_tabs, delim, citado in pendientes:
            if not delim or i >= len(lineas):
                continue
            # ``1 << n`` en un ``python -c`` de varias líneas: sin cierre no se toma por heredoc.
            if (
                not citado
                and not re.fullmatch(r"[A-Z_][A-Z0-9_]*", delim)
                and not any((x.lstrip("\t") if quita_tabs else x).rstrip() == delim for x in lineas[i:])
            ):
                continue
            cuerpo: list[str] = []
            cerrado = False
            j = i
            while j < len(lineas):
                prueba = lineas[j].lstrip("\t") if quita_tabs else lineas[j]
                if prueba.rstrip() == delim:
                    cerrado = True
                    break
                cuerpo.append(lineas[j])
                j += 1
            if cerrado or j >= len(lineas):
                encontrados.append(Heredoc(linea, delim, cuerpo))
                i = j + 1
        # Si el cuerpo consumió líneas, el cierre ya se saltó con ``i``.
    return encontrados, "\n".join(resto)


def _es_interprete(linea: str) -> str | None:
    """Nombre del intérprete que recibe el heredoc en la línea del operador, si hay uno."""
    corte = linea.find("<<") if "<<" in linea else len(linea)
    for crudo in (linea[:corte], linea[corte + 2 :]):
        # Una palabra dentro de una cadena completa («-m "usa python"») no es una orden.
        trozo = re.sub(r"\"[^\"\n]*\"|'[^'\n]*'", " ", crudo)
        for m in re.finditer(r"(?:^|[\s|;&(`/\\=])([A-Za-z][\w.]*?)(?:\.exe)?(?=[\s|;&)`]|$)", trozo):
            nombre = m.group(1).lower()
            if nombre in INTERPRETES:
                return nombre
    return None


def evaluar_heredoc(orden: str) -> tuple[str, str, str] | None:
    """(regla, motivo, ejemplo) si la orden debe rechazarse por un heredoc; ``None`` si pasa."""
    heredocs, _ = encontrar_heredocs(orden)
    for h in heredocs:
        interprete = _es_interprete(h.linea_operador)
        if interprete:
            return (
                "interprete",
                f"un heredoc alimenta a `{interprete}` ({len(h.cuerpo)} líneas)",
                "python scripts/mi_guion.py",
            )
        if _REDIRECCION_FUENTE.search(h.linea_operador):
            return (
                "archivo_fuente",
                "un heredoc escribe un archivo fuente",
                "python -m pytest ruta/al/archivo",
            )
        if len(h.cuerpo) > MAX_LINEAS_HEREDOC:
            return (
                "largo",
                f"un heredoc de {len(h.cuerpo)} líneas pasa de {MAX_LINEAS_HEREDOC}",
                "gh ... --body-file archivo.md",
            )
    return None


# ---------------------------------------------------------------- guarda de cuenta


def _tokens(orden: str) -> list[list[str]]:
    """Segmentos de la orden (separados por ``; & | ( )`` fuera de comillas), ya en palabras."""
    _, sin_cuerpos = encontrar_heredocs(orden)
    texto = sin_cuerpos.replace("\\\r\n", " ").replace("\\\n", " ").replace("\n", " ; ")
    lexer = shlex.shlex(texto, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    segmentos: list[list[str]] = [[]]
    try:
        for palabra in lexer:
            if palabra and set(palabra) <= set(";&|()"):
                segmentos.append([])
            else:
                segmentos[-1].append(palabra)
    except ValueError:
        # Comillas sin cerrar: partir sin respetarlas es mejor que no mirar.
        segmentos = [s.split() for s in re.split(r"[;&|()]+", texto)]
    return [s for s in segmentos if s]


def _sin_prefijo(segmento: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """Asignaciones de entorno iniciales y el resto de la orden (tras ``env``/``command``)."""
    entorno: dict[str, str] = {}
    i = 0
    while i < len(segmento):
        palabra = segmento[i]
        m = _ASIGNACION.match(palabra)
        if m:
            entorno[m.group(1)] = m.group(2)
        elif Path(palabra.replace("\\", "/")).name in ("env", "command", "builtin", "exec"):
            pass
        else:
            break
        i += 1
    return entorno, list(segmento[i:])


def _nombre(palabra: str) -> str:
    base = Path(palabra.replace("\\", "/")).name.lower()
    return base[:-4] if base.endswith(".exe") else base


def _opcion(args: Sequence[str], *nombres: str) -> str | None:
    """Valor de una opción ``-X v``, ``--x=v`` o ``-Xv`` (la primera que aparezca)."""
    for i, a in enumerate(args):
        for n in nombres:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if n.startswith("--") and a.startswith(n + "="):
                return a[len(n) + 1 :]
            if not n.startswith("--") and len(a) > len(n) and a.startswith(n) and not a.startswith("--"):
                return a[len(n) :]
    return None


def _es_escritura_gh(args: Sequence[str]) -> str | None:
    """Descripción de la escritura si los argumentos de ``gh`` (sin ``gh``) escriben; si no, ``None``."""
    posicionales = [a for a in args if not a.startswith("-")]
    if not posicionales:
        return None
    grupo = posicionales[0]
    accion = posicionales[1] if len(posicionales) > 1 else ""
    if grupo == "pr" and accion in {
        "create",
        "comment",
        "merge",
        "edit",
        "close",
        "review",
        "reopen",
        "ready",
    }:
        return f"gh pr {accion}"
    if grupo == "issue" and accion in {"create", "comment", "edit", "close", "reopen", "delete", "transfer"}:
        return f"gh issue {accion}"
    if grupo == "project" and accion.startswith("item-"):
        return f"gh project {accion}"
    if grupo == "release" and accion not in {"list", "view", "download"}:
        return f"gh release {accion or ''}".strip()
    if grupo == "api":
        metodo = (_opcion(args, "-X", "--method") or "").upper()
        if metodo in {"POST", "PATCH", "PUT", "DELETE"}:
            return f"gh api -X {metodo}"
        if metodo == "GET":
            return None
        campos = [a for a in args if a in {"-f", "-F", "--field", "--raw-field", "--input"}]
        campos += [a for a in args if re.match(r"^-[fF].+", a) and not a.startswith("--")]
        if campos:
            punto = posicionales[1] if len(posicionales) > 1 else ""
            texto = " ".join(args).lower()
            if punto == "graphql" and "mutation" not in texto:
                return None
            return "gh api con campos (-f/-F)"
    return None


def _apunta_a_otro_repo(args: Sequence[str]) -> bool:
    repo = _opcion(args, "-R", "--repo")
    if repo and "agents_learning_loops" not in repo.lower():
        return True
    for a in args:
        m = re.match(r"^/?repos/([^/\s]+/[^/\s]+)", a)
        if m and m.group(1).lower() != REPOSITORIO:
            return True
    return False


def operacion_con_cuenta(orden: str) -> list[tuple[str, dict[str, str]]]:
    """Escrituras de la orden que dependen de la cuenta: (descripción, entorno de la orden)."""
    resultado: list[tuple[str, dict[str, str]]] = []
    for segmento in _tokens(orden):
        entorno, resto = _sin_prefijo(segmento)
        if not resto:
            continue
        nombre = _nombre(resto[0])
        if nombre == "gh":
            args = resto[1:]
            descripcion = _es_escritura_gh(args)
            if descripcion and not _apunta_a_otro_repo(args):
                resultado.append((descripcion, entorno))
        elif nombre == "git":
            args = resto[1:]
            sin_opciones: list[str] = []
            saltar = False
            for a in args:
                if saltar:
                    saltar = False
                    continue
                if a in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
                    saltar = True
                    continue
                if not a.startswith("-"):
                    sin_opciones.append(a)
            if sin_opciones[:1] == ["push"]:
                resultado.append(("git push", entorno))
    return resultado


def es_este_repositorio(cwd: str) -> bool | None:
    """``True``/``False`` según el remoto ``origin`` del directorio; ``None`` si no se pudo saber."""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd or ".", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=TOPE_SUBPROCESO,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return REPOSITORIO in proc.stdout.strip().lower().removesuffix(".git").replace(":", "/")


def _directorios_config_gh(entorno: Mapping[str, str]) -> list[Path]:
    candidatos: list[Path] = []
    if entorno.get("GH_CONFIG_DIR"):
        candidatos.append(Path(entorno["GH_CONFIG_DIR"]))
    if entorno.get("XDG_CONFIG_HOME"):
        candidatos.append(Path(entorno["XDG_CONFIG_HOME"]) / "gh")
    if entorno.get("APPDATA"):
        candidatos.append(Path(entorno["APPDATA"]) / "GitHub CLI")
    candidatos.append(Path.home() / ".config" / "gh")
    return candidatos


def cuenta_activa_llavero(entorno: Mapping[str, str]) -> str | None:
    """Cuenta activa de ``gh`` leída de ``hosts.yml`` (sin red); ``None`` si no se puede saber."""
    for carpeta in _directorios_config_gh(entorno):
        archivo = carpeta / "hosts.yml"
        if not archivo.is_file():
            continue
        try:
            lineas = archivo.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        en_github = False
        for linea in lineas:
            if re.match(r"^github\.com:\s*$", linea):
                en_github = True
            elif re.match(r"^\S", linea):
                en_github = False
            m = re.match(r"^\s{1,4}user:\s*(\S+)\s*$", linea)
            if en_github and m:
                return m.group(1).strip("'\"")
    return None


def token_propio(entorno: Mapping[str, str]) -> str | None:
    """Token de la cuenta del proyecto, del llavero local (sin red); ``None`` si no se obtiene."""
    forzado = entorno.get("GUARDA_PREVIA_TOKEN_PROPIO")
    if forzado is not None:
        return forzado or None
    try:
        proc = subprocess.run(
            ["gh", "auth", "token", "--user", CUENTA],
            capture_output=True,
            text=True,
            timeout=TOPE_SUBPROCESO,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def evaluar_cuenta(orden: str, cwd: str, entorno: Mapping[str, str]) -> tuple[str | None, str | None]:
    """(``motivo``, ``regla``) si debe rechazarse; (``None``, nota) si pasa. La nota explica un «dudoso»."""
    operaciones = operacion_con_cuenta(orden)
    if not operaciones:
        return None, None
    este = es_este_repositorio(cwd)
    if este is False:
        return None, None
    if este is None:
        return None, "no se pudo saber si el directorio de trabajo es este repositorio"
    for descripcion, entorno_orden in operaciones:
        ficha = entorno_orden.get("GH_TOKEN") or entorno_orden.get("GITHUB_TOKEN")
        en_orden = "GH_TOKEN" in entorno_orden or "GITHUB_TOKEN" in entorno_orden
        en_entorno = entorno.get("GH_TOKEN") or entorno.get("GITHUB_TOKEN")
        if en_orden or en_entorno:
            declarada = re.search(
                r"gh\s+auth\s+token\s+(?:-\w+\s+\S+\s+)*(?:--user|-u)[ =](\S+)", ficha or ""
            )
            if declarada:
                usuario = declarada.group(1).strip("'\")")
                if usuario.lower() != CUENTA:
                    return f"{descripcion} con el token de la cuenta {usuario}", "token_ajeno"
                continue
            valor = ficha if en_orden else en_entorno
            if not valor or "$" in valor:
                return None, "token no resoluble sin ejecutar la orden"
            propio = token_propio(entorno)
            if propio is None:
                return None, "no se pudo leer el token propio del llavero"
            if valor != propio:
                return f"{descripcion} con un token que no es el de la cuenta {CUENTA}", "token_ajeno"
            continue
        activa = cuenta_activa_llavero(entorno)
        if activa is None:
            return None, "no se pudo leer la cuenta activa de gh"
        if activa.lower() != CUENTA:
            return f"{descripcion} sin GH_TOKEN y la cuenta activa del llavero es {activa}", "cuenta_activa"
    return None, None


# ---------------------------------------------------------------- registro


def ruta_registro(entorno: Mapping[str, str]) -> Path:
    if entorno.get("GUARDA_PREVIA_REGISTRO"):
        return Path(entorno["GUARDA_PREVIA_REGISTRO"])
    raiz = entorno.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parent.parent)
    return Path(raiz) / ".claude" / "guarda_previa.jsonl"


def _muestra(orden: str) -> str:
    """Primeros 60 caracteres de la primera línea, sin secretos."""
    primera = orden.strip().splitlines()[0] if orden.strip() else ""
    return _SECRETO.sub(lambda m: (m.group(1) or "") + "***", primera)[:60]


def registrar(entorno: Mapping[str, str], tipo: str, regla: str, orden: str = "", **extra: Any) -> None:
    """Añade una línea al registro; un fallo al escribir no tumba el gancho."""
    ficha = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tipo": tipo,
        "regla": regla,
        "inicio": _muestra(orden),
        **extra,
    }
    try:
        ruta = ruta_registro(entorno)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ficha, ensure_ascii=False) + "\n")
    except OSError:
        pass


def contar(entorno: Mapping[str, str], salida: TextIO) -> int:
    """Imprime el recuento del registro por tipo y regla. Devuelve 0 (también sin registro)."""
    ruta = ruta_registro(entorno)
    if not ruta.is_file():
        salida.write(f"Sin registro todavía ({ruta}): ningún rechazo contado.\n")
        return 0
    cuentas: Counter[tuple[str, str]] = Counter()
    ultimo = ""
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            f = json.loads(linea)
        except json.JSONDecodeError:
            continue
        cuentas[(str(f.get("tipo")), str(f.get("regla")))] += 1
        ultimo = str(f.get("ts", ""))
    salida.write(f"Registro de la guarda previa: {ruta}\n")
    total_rechazos = sum(n for (t, _), n in cuentas.items() if t == "rechazo")
    salida.write(f"rechazos: {total_rechazos}\n")
    for (tipo, regla), n in sorted(cuentas.items()):
        salida.write(f"  {tipo:<8} {regla:<16} {n}\n")
    salida.write(f"último: {ultimo}\n")
    return 0


# ---------------------------------------------------------------- gancho


def decidir(evento: Mapping[str, Any], entorno: Mapping[str, str]) -> tuple[int, str]:
    """(código de salida, mensaje) para un evento ``PreToolUse``. 0 con mensaje vacío = pasa."""
    if evento.get("tool_name") not in (None, "Bash"):
        return 0, ""
    entrada = evento.get("tool_input")
    orden = entrada.get("command") if isinstance(entrada, Mapping) else None
    if not isinstance(orden, str) or not orden.strip():
        return 0, ""
    cwd = str(evento.get("cwd") or os.getcwd())

    heredoc = evaluar_heredoc(orden)
    if heredoc:
        regla, motivo, ejemplo = heredoc
        registrar(entorno, "rechazo", f"heredoc:{regla}", orden)
        return 2, MENSAJE_HEREDOC.format(motivo=motivo, ejemplo=ejemplo)

    motivo_cuenta, nota = evaluar_cuenta(orden, cwd, entorno)
    if motivo_cuenta:
        registrar(entorno, "rechazo", f"cuenta:{nota}", orden)
        return 2, MENSAJE_CUENTA.format(motivo=motivo_cuenta)
    if nota:
        registrar(entorno, "dudoso", "cuenta", orden, nota=nota)
        return 0, f"guarda previa: dejo pasar la orden ({nota})."
    return 0, ""


def main(argv: Sequence[str] | None = None, entrada: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guardas previas a una orden de Bash (gancho PreToolUse).")
    parser.add_argument("--contar", action="store_true", help="lee el registro de rechazos y sale")
    args = parser.parse_args(argv)
    entorno = dict(os.environ)
    if args.contar:
        return contar(entorno, sys.stdout)

    resultado: list[tuple[int, str]] = []

    def trabajar() -> None:
        try:
            texto = (entrada or sys.stdin).read()
            evento = json.loads(texto) if texto.strip() else {}
            resultado.append(decidir(evento if isinstance(evento, dict) else {}, entorno))
        except Exception as error:  # el gancho nunca debe romper una orden
            registrar(entorno, "falla", type(error).__name__)
            resultado.append((0, f"guarda previa: falló ({type(error).__name__}); dejo pasar la orden."))

    hilo = threading.Thread(target=trabajar, daemon=True)
    hilo.start()
    hilo.join(TOPE_SEGUNDOS)
    if hilo.is_alive():
        registrar(entorno, "falla", "tope")
        codigo, mensaje = 0, f"guarda previa: pasó de {TOPE_SEGUNDOS:g} s; dejo pasar la orden."
    else:
        codigo, mensaje = resultado[0]
    if codigo == 2:
        sys.stderr.write(mensaje + "\n")
    elif mensaje:
        sys.stderr.write(mensaje + "\n")
        sys.stdout.write(json.dumps({"systemMessage": mensaje}, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(codigo)  # un hilo atascado no debe retener el proceso


if __name__ == "__main__":
    sys.exit(main())
