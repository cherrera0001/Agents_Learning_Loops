"""Guardas previas a una orden de Bash (gancho ``PreToolUse`` de Claude Code, issue #186).

Dos guardas que el texto no logró hacer cumplir. Rechazan solo lo que pueden decidir con seguridad y
cuentan lo dudoso: un falso rechazo cuesta más que un fallo que se escapa.

1. **Heredoc.** Rechaza un heredoc cuya orden simple ejecuta un intérprete (``python``, ``node``, ``bash``...,
   también ``cat <<EOF | python -``), que escribe un archivo fuente (``cat > x.py <<EOF``) o cuyo cuerpo
   pasa de ``MAX_LINEAS_HEREDOC`` líneas.
2. **Cuenta de GitHub.** Rechaza una orden ``gh`` de escritura (lista explícita de pares grupo-verbo) en
   este repositorio cuando la orden no menciona ``GH_TOKEN`` en ninguna parte y la cuenta activa de ``gh``
   no es ``cherrera0001``, o cuando nombra otra cuenta en ``gh auth token --user`` (esto último también
   si no se logra saber de qué repositorio es el directorio, #206). ``git push`` nunca se
   rechaza: se cuenta como «push visto» (git usa su propio gestor de credenciales).

Contrato del gancho: lee por stdin (bytes, UTF-8) el JSON de Claude Code (``tool_name``,
``tool_input.command``, ``cwd``). Para rechazar escribe por stdout la decisión
``hookSpecificOutput.permissionDecision = "deny"`` y **sale siempre con 0**: ninguna avería puede
bloquear una orden. Cualquier excepción, entrada rota o tope (``TOPE_SEGUNDOS``) sale con 0 sin decisión.

El registro local ``.claude/guarda_previa.jsonl`` (ignorado por git) guarda solo hora, regla, veredicto y
el nombre del ejecutable; nunca texto de la orden. Se lee con::

    python -m scripts.guarda_previa --contar

Solo biblioteca estándar. Solo cubre la herramienta Bash de Claude Code: no cubre PowerShell, Codex ni
otros agentes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

CUENTA = "cherrera0001"
REPOSITORIO = "cherrera0001/agents_learning_loops"
# Un heredoc de texto plano más largo que esto se rechaza. 29 de 152 cuerpos de commit del historial
# pasan de 20 líneas y 6 de 60 (casi todos fusiones automáticas): 60 deja pasar un mensaje o un archivo de
# datos razonable y frena los cuerpos enteros de issue o de parche.
MAX_LINEAS_HEREDOC = 60
# Tope total del guion. El de ``.claude/settings.json`` es mayor (10 s) para que mande este.
TOPE_SEGUNDOS = 6.0
TOPE_SUBPROCESO = 2.0

VEREDICTO_RECHAZO = "rechazo"
VEREDICTO_DUDOSO = "pasa-dudoso"
VEREDICTO_PUSH = "push-visto"
VEREDICTO_FALLA = "falla"

_INTERPRETE = re.compile(
    r"^(?:python\d*(?:\.\d+)*|py|ipython\d*|node(?:js)?|bash|sh|zsh|dash|perl|ruby|pwsh|powershell|deno|bun|php)$"
)
_ENVOLTORIOS = frozenset({"env", "command", "exec", "time", "nohup", "winpty", "sudo", "builtin"})
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
_REDIRECCION_FUENTE = re.compile(
    r"(?:>>?|\btee(?:\s+-a)?)\s*['\"]?[^\s'\"|;&<>]*\.(?:" + "|".join(EXTENSIONES_FUENTE) + r")\b",
    re.IGNORECASE,
)
_OPERADOR_HEREDOC = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?(\w[\w.-]*))")
_ASIGNACION = re.compile(r"^[A-Za-z_]\w*=")
_TOKEN_LITERAL = re.compile(r"(?:GH|GITHUB)_TOKEN=[\"']?(?![\"']?[$(`])[A-Za-z0-9_]{8,}")

MENSAJE_HEREDOC = (
    "RECHAZADA por la guarda previa (#186): {motivo}. En Git Bash sobre Windows un heredoc así rompe las "
    "secuencias de escape o el cierre de comillas. En su lugar: escribe el archivo con la herramienta de "
    "edición (Write o Edit) y ejecútalo con una orden corta ({ejemplo}). Si la orden era legítima, "
    "redúcela o pasa el texto a un archivo. Esta guarda no cubre PowerShell."
)
EJEMPLO_LARGO = {
    "commit": "git commit -F archivo.txt",
    "gh": "gh ... --body-file archivo.md",
    "otro": "un archivo escrito con Write y leído por la orden",
}
MENSAJE_CUENTA = (
    "RECHAZADA por la guarda previa (#186): {motivo}. Esta escritura debe salir con la cuenta "
    f"{CUENTA}. Fija la cuenta en la propia orden, sin `gh auth switch`: "
    f'GH_TOKEN="$(gh auth token --user {CUENTA})" gh ... Las lecturas no se frenan.'
)

# ---------------------------------------------------------------- análisis de la orden


@dataclass(eq=False)
class Heredoc:
    """Un heredoc: su delimitador, su cuerpo y el segmento (orden simple) al que pertenece."""

    delimitador: str
    citado: bool
    quita_tabs: bool
    segmento: Segmento
    cuerpo: list[str] = field(default_factory=list)
    real: bool = True


@dataclass(eq=False)
class Segmento:
    """Una orden simple: el texto entre separadores (``&& || ; | &`` y salto de línea)."""

    ctx: int
    sep: str
    texto: str = ""
    heredocs: list[Heredoc] = field(default_factory=list)


def _leer_cuerpos(lineas: list[str], inicio: int, pendientes: list[Heredoc]) -> int:
    """Consume los cuerpos de los heredocs pendientes; devuelve la siguiente línea a leer."""
    pos = inicio
    for h in pendientes:
        j = pos
        while j < len(lineas):
            linea = lineas[j].lstrip("\t") if h.quita_tabs else lineas[j]
            if linea.rstrip() == h.delimitador:
                break
            j += 1
        if j < len(lineas):
            h.cuerpo = lineas[pos:j]
            pos = j + 1
        elif h.citado or re.fullmatch(r"[A-Z_][A-Z0-9_]*", h.delimitador):
            h.cuerpo = lineas[pos:]
            pos = len(lineas)
        else:
            h.real = False  # ``1 << n`` sin cierre: no es un heredoc
    return pos


def analizar(orden: str) -> tuple[list[Segmento], list[Heredoc]]:
    """Parte la orden en órdenes simples (respetando comillas y ``$(...)``) y halla sus heredocs.

    Un ``<<`` es un heredoc solo si está fuera de comillas, tiene delimitador y hay un salto de línea
    posterior con su cierre (o, sin cierre, un delimitador citado o en mayúsculas).
    """
    t = orden.replace("\r\n", "\n")
    n = len(t)
    segmentos: list[Segmento] = []
    siguiente = 0

    def nuevo(ctx: int, sep: str) -> Segmento:
        s = Segmento(ctx, sep)
        segmentos.append(s)
        return s

    pila: list[dict[str, Any]] = [{"fin": None, "q": None, "id": 0, "seg": nuevo(0, "")}]
    pendientes: list[Heredoc] = []
    todos: list[Heredoc] = []
    i = 0

    def empujar(fin: str) -> None:
        nonlocal siguiente
        siguiente += 1
        pila.append({"fin": fin, "q": None, "id": siguiente, "seg": nuevo(siguiente, "sub")})

    while i < n:
        c = t[i]
        ctx = pila[-1]
        seg: Segmento = ctx["seg"]
        q = ctx["q"]
        if q == "'":
            seg.texto += c
            if c == "'":
                ctx["q"] = None
            i += 1
        elif q == '"':
            if c == "\\" and i + 1 < n:
                seg.texto += t[i : i + 2]
                i += 2
            elif c == '"':
                ctx["q"] = None
                seg.texto += c
                i += 1
            elif t.startswith("$(", i):
                empujar(")")
                i += 2
            elif c == "`":
                empujar("`")
                i += 1
            else:
                seg.texto += c
                i += 1
        elif c == "\\":
            if t.startswith("\\\n", i):
                seg.texto += " "
                i += 2
            else:
                seg.texto += t[i : i + 2]
                i += 2
        elif c in "'\"":
            ctx["q"] = c
            seg.texto += c
            i += 1
        elif t.startswith("$(", i):
            empujar(")")
            i += 2
        elif c == "`":
            if ctx["fin"] == "`" and len(pila) > 1:
                pila.pop()
            else:
                empujar("`")
            i += 1
        elif c == ")" and ctx["fin"] == ")" and len(pila) > 1:
            pila.pop()
            i += 1
        elif c == "\n":
            if pendientes:
                lineas = t[i + 1 :].split("\n")
                usadas = _leer_cuerpos(lineas, 0, pendientes)
                pendientes = []
                i = min(n, i + 1 + sum(len(x) + 1 for x in lineas[:usadas]))
            else:
                i += 1
            ctx["seg"] = nuevo(ctx["id"], "\n")
        elif t.startswith("&&", i) or t.startswith("||", i):
            ctx["seg"] = nuevo(ctx["id"], t[i : i + 2])
            i += 2
        elif c in "|;&()":
            ctx["seg"] = nuevo(ctx["id"], c)
            i += 1
        elif t.startswith("<<<", i):
            seg.texto += "<<<"
            i += 3
        elif t.startswith("<<", i):
            m = _OPERADOR_HEREDOC.match(t, i)
            if m:
                delim = m.group(2) or m.group(3) or m.group(4)
                h = Heredoc(delim, bool(m.group(2) or m.group(3)), m.group(1) == "-", seg)
                seg.heredocs.append(h)
                pendientes.append(h)
                todos.append(h)
                seg.texto += t[i : m.end()]
                i = m.end()
            else:
                seg.texto += "<<"
                i += 2
        else:
            seg.texto += c
            i += 1
    for h in pendientes:
        h.real = False  # sin salto de línea posterior no hay cuerpo
    return segmentos, [h for h in todos if h.real]


def _palabras(texto: str) -> list[str]:
    """Palabras de una orden simple, sin las comillas (las barras invertidas se respetan)."""
    palabras: list[str] = []
    actual = ""
    comilla = ""
    hay = False
    for c in texto:
        if comilla:
            if c == comilla:
                comilla = ""
            else:
                actual += c
        elif c in "'\"":
            comilla = c
            hay = True
        elif c.isspace():
            if hay or actual:
                palabras.append(actual)
            actual = ""
            hay = False
        else:
            actual += c
    if hay or actual:
        palabras.append(actual)
    return palabras


def _base(palabra: str) -> str:
    nombre = palabra.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return nombre[:-4] if nombre.endswith(".exe") else nombre


def ejecutable(texto: str) -> tuple[str, list[str]]:
    """Nombre base del ejecutable de una orden simple y sus argumentos.

    Quita asignaciones de entorno, comillas y ruta, y atraviesa envoltorios (``env``, ``uv run``...).
    """
    p = _palabras(texto)
    i = 0
    while i < len(p):
        w = p[i]
        nombre = _base(w)
        if _ASIGNACION.match(w):
            i += 1
        elif nombre in _ENVOLTORIOS or (nombre == "uv" and p[i + 1 : i + 2] == ["run"]):
            i += 2 if nombre == "uv" else 1
            while i < len(p) and (p[i].startswith("-") or _ASIGNACION.match(p[i])):
                i += 1
        else:
            return nombre, p[i + 1 :]
    return "", []


def _cadena(segmentos: Sequence[Segmento], h: Heredoc) -> list[Segmento]:
    """La orden del heredoc y las que reciben su salida por tubería."""
    cadena = [h.segmento]
    i = segmentos.index(h.segmento)
    for s in segmentos[i + 1 :]:
        if s.ctx != h.segmento.ctx:
            continue
        if s.sep != "|":
            break
        cadena.append(s)
    return cadena


def evaluar_heredoc(orden: str) -> tuple[str, str, str, str] | None:
    """(regla, motivo, ejemplo, ejecutable) si debe rechazarse por un heredoc; ``None`` si pasa."""
    segmentos, heredocs = analizar(orden)
    for h in heredocs:
        cadena = _cadena(segmentos, h)
        for s in cadena:
            nombre, _ = ejecutable(s.texto)
            if _INTERPRETE.match(nombre):
                return (
                    "interprete",
                    f"un heredoc alimenta a `{nombre}` ({len(h.cuerpo)} líneas)",
                    "python scripts/mi_guion.py",
                    nombre,
                )
        if any(_REDIRECCION_FUENTE.search(s.texto) for s in cadena):
            return (
                "archivo_fuente",
                "un heredoc escribe un archivo fuente",
                "python -m pytest ruta/al/archivo",
                ejecutable(h.segmento.texto)[0],
            )
        if len(h.cuerpo) > MAX_LINEAS_HEREDOC:
            nombres = [ejecutable(s.texto)[0] for s in segmentos]
            clase = (
                "commit" if "commit" in orden and "git" in nombres else "gh" if "gh" in nombres else "otro"
            )
            return (
                "largo",
                f"un heredoc de {len(h.cuerpo)} líneas pasa de {MAX_LINEAS_HEREDOC}",
                EJEMPLO_LARGO[clase],
                ejecutable(h.segmento.texto)[0],
            )
    return None


# ---------------------------------------------------------------- guarda de cuenta

ESCRITURAS_GH: dict[str, frozenset[str]] = {
    "pr": frozenset({"create", "comment", "merge", "edit", "close", "reopen", "review", "ready"}),
    "issue": frozenset(
        {"create", "comment", "edit", "close", "reopen", "pin", "unpin", "delete", "transfer"}
    ),
    "release": frozenset({"create", "edit", "delete", "upload"}),
    "label": frozenset({"create", "edit", "delete"}),
    "project": frozenset(
        {
            "item-add",
            "item-edit",
            "item-delete",
            "item-archive",
            "item-create",
            "field-create",
            "field-delete",
            "edit",
            "close",
            "delete",
        }
    ),
    "workflow": frozenset({"run", "enable", "disable"}),
    "run": frozenset({"cancel", "rerun", "delete"}),
    "repo": frozenset({"edit", "delete", "rename", "archive"}),
    "secret": frozenset({"set", "delete"}),
    "variable": frozenset({"set", "delete"}),
}


def _opcion(args: Sequence[str], *nombres: str) -> str | None:
    """Valor de una opción ``-X v``, ``--x=v`` o ``-Xv``."""
    for i, a in enumerate(args):
        for n in nombres:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if n.startswith("--") and a.startswith(n + "="):
                return a[len(n) + 1 :]
            if not n.startswith("--") and len(a) > len(n) and a.startswith(n) and not a.startswith("--"):
                return a[len(n) :]
    return None


def _posicionales(args: Sequence[str]) -> list[str]:
    resultado: list[str] = []
    saltar = False
    for a in args:
        if saltar:
            saltar = False
        elif a in {"-R", "--repo"}:
            saltar = True
        elif not a.startswith("-"):
            resultado.append(a)
    return resultado


def es_escritura_gh(args: Sequence[str]) -> str | None:
    """Descripción de la escritura si los argumentos de ``gh`` (sin ``gh``) escriben; si no, ``None``."""
    pos = _posicionales(args)
    if not pos:
        return None
    grupo = pos[0]
    accion = pos[1] if len(pos) > 1 else ""
    if accion in ESCRITURAS_GH.get(grupo, frozenset()):
        return f"gh {grupo} {accion}"
    if grupo == "api":
        metodo = (_opcion(args, "-X", "--method") or "").upper()
        if metodo == "GET":
            return None
        if metodo:
            return f"gh api -X {metodo}"
        campos = [a for a in args if a in {"-f", "-F", "--field", "--raw-field", "--input"}]
        campos += [a for a in args if re.match(r"^-[fF][^-]", a)]
        campos += [a for a in args if re.match(r"^--(?:field|raw-field|input)=", a)]
        if campos:
            if accion == "graphql" and "mutation" not in " ".join(args).lower():
                return None
            return "gh api con campos (-f/-F)"
    return None


def apunta_a_otro_repo(args: Sequence[str]) -> bool:
    repo = _opcion(args, "-R", "--repo")
    if repo and "agents_learning_loops" not in repo.lower():
        return True
    for a in args:
        m = re.match(r"^/?repos/([^/\s]+/[^/\s]+)", a)
        if m and m.group(1).lower() != REPOSITORIO:
            return True
    return False


@dataclass
class Observacion:
    """Lo que la orden hace que interesa a la guarda de cuenta."""

    escrituras: list[tuple[str, list[str]]] = field(default_factory=list)
    push: bool = False
    cambia_directorio: bool = False
    # Cuentas de ``gh auth token --user X`` que son una orden (simple o dentro de ``$(...)``), no texto.
    usuarios_token: list[str] = field(default_factory=list)


def observar(orden: str) -> Observacion:
    obs = Observacion()
    segmentos, _ = analizar(orden)
    for s in segmentos:
        nombre, args = ejecutable(s.texto)
        if nombre == "gh":
            if args[:2] == ["auth", "token"]:
                usuario = _opcion(args, "--user", "-u")
                if usuario:
                    obs.usuarios_token.append(usuario)
            descripcion = es_escritura_gh(args)
            if descripcion:
                obs.escrituras.append((descripcion, args))
        elif nombre == "git":
            sin: list[str] = []
            saltar = False
            for a in args:
                if saltar:
                    saltar = False
                elif a in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}:
                    saltar = True
                    if a in {"-C", "--git-dir", "--work-tree"}:
                        obs.cambia_directorio = True
                elif not a.startswith("-"):
                    sin.append(a)
            if sin[:1] == ["push"]:
                obs.push = True
        elif nombre in {"cd", "pushd"}:
            obs.cambia_directorio = True
    return obs


def es_este_repositorio(cwd: str) -> bool | None:
    """``True``/``False`` según el remoto ``origin`` del directorio; ``None`` si no se pudo saber."""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd or ".", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TOPE_SUBPROCESO,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return REPOSITORIO in proc.stdout.strip().lower().removesuffix(".git").replace(":", "/")


def _carpetas_config_gh(entorno: Mapping[str, str]) -> list[Path]:
    candidatas: list[Path] = []
    if entorno.get("GH_CONFIG_DIR"):
        candidatas.append(Path(entorno["GH_CONFIG_DIR"]))
    if entorno.get("XDG_CONFIG_HOME"):
        candidatas.append(Path(entorno["XDG_CONFIG_HOME"]) / "gh")
    if entorno.get("APPDATA"):
        candidatas.append(Path(entorno["APPDATA"]) / "GitHub CLI")
    candidatas.append(Path.home() / ".config" / "gh")
    return candidatas


def cuenta_activa_llavero(entorno: Mapping[str, str]) -> str | None:
    """Cuenta activa de ``gh`` leída del ``hosts.yml`` de ``github.com`` (sin red)."""
    for carpeta in _carpetas_config_gh(entorno):
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


@dataclass
class Veredicto:
    """Resultado de la guarda de cuenta: ``rechazo``, ``pasa-dudoso``, ``push-visto`` o ninguno."""

    tipo: str
    regla: str
    ejecutable: str
    motivo: str = ""


def evaluar_cuenta(orden: str, cwd: str, entorno: Mapping[str, str]) -> Veredicto | None:
    """Veredicto de la guarda de cuenta, o ``None`` si la orden no la concierne o pasa sin más."""
    obs = observar(orden)
    if not obs.escrituras:
        return Veredicto(VEREDICTO_PUSH, "cuenta:push", "git") if obs.push else None
    este = es_este_repositorio(cwd)
    if este is False:
        return None
    escrituras = [e for e in obs.escrituras if not apunta_a_otro_repo(e[1])]
    if not escrituras:
        return None if este else Veredicto(VEREDICTO_DUDOSO, "cuenta:repo_desconocido", "gh")
    descripcion = escrituras[0][0]
    if obs.cambia_directorio:
        regla = "cuenta:cambia_directorio" if este else "cuenta:repo_desconocido"
        return Veredicto(VEREDICTO_DUDOSO, regla, "gh")
    # Un token de otra cuenta es una violación aunque no se sepa de qué repositorio es el directorio
    # (git lento, ausente o directorio inexistente, #206): solo ``este is False`` la deja pasar.
    for usuario in obs.usuarios_token:
        if usuario.lower() != CUENTA:
            return Veredicto(
                VEREDICTO_RECHAZO,
                "cuenta:token_ajeno",
                "gh",
                f"{descripcion} con el token de la cuenta {usuario}",
            )
    if este is None:
        return Veredicto(VEREDICTO_DUDOSO, "cuenta:repo_desconocido", "gh")
    if "GH_TOKEN" in orden or "GITHUB_TOKEN" in orden:
        if _TOKEN_LITERAL.search(orden):
            return Veredicto(VEREDICTO_DUDOSO, "cuenta:token_literal", "gh")
        return None
    if entorno.get("GH_TOKEN") or entorno.get("GITHUB_TOKEN"):
        return Veredicto(VEREDICTO_DUDOSO, "cuenta:token_en_entorno", "gh")
    activa = cuenta_activa_llavero(entorno)
    if activa is None:
        return Veredicto(VEREDICTO_DUDOSO, "cuenta:activa_desconocida", "gh")
    if activa.lower() != CUENTA:
        return Veredicto(
            VEREDICTO_RECHAZO,
            "cuenta:cuenta_activa",
            "gh",
            f"{descripcion} sin GH_TOKEN y la cuenta activa del llavero es {activa}",
        )
    return None


# ---------------------------------------------------------------- registro


def ruta_registro(entorno: Mapping[str, str]) -> Path:
    if entorno.get("GUARDA_PREVIA_REGISTRO"):
        return Path(entorno["GUARDA_PREVIA_REGISTRO"])
    raiz = entorno.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parent.parent)
    return Path(raiz) / ".claude" / "guarda_previa.jsonl"


def registrar(entorno: Mapping[str, str], veredicto: str, regla: str, ejecutable_: str = "") -> None:
    """Añade una línea: hora, regla, veredicto y nombre del ejecutable. Nunca texto de la orden."""
    ficha = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "regla": regla,
        "veredicto": veredicto,
        "ejecutable": ejecutable_[:40],
    }
    try:
        ruta = ruta_registro(entorno)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ficha, ensure_ascii=False) + "\n")
    except OSError:
        pass


def contar(entorno: Mapping[str, str], salida: TextIO) -> int:
    """Imprime el recuento del registro por veredicto y regla. Devuelve 0 (también sin registro)."""
    ruta = ruta_registro(entorno)
    if not ruta.is_file():
        salida.write(f"Sin registro todavia ({ruta}): ningun rechazo contado.\n")
        return 0
    cuentas: Counter[tuple[str, str]] = Counter()
    ultimo = ""
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            f = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if not isinstance(f, dict):
            continue
        cuentas[(str(f.get("veredicto")), str(f.get("regla")))] += 1
        ultimo = str(f.get("ts", ""))
    por_veredicto: Counter[str] = Counter()
    for (veredicto, _), n in cuentas.items():
        por_veredicto[veredicto] += n
    salida.write(f"Registro de la guarda previa: {ruta}\n")
    salida.write(f"rechazos: {por_veredicto[VEREDICTO_RECHAZO]}\n")
    salida.write(f"pasa-dudoso: {por_veredicto[VEREDICTO_DUDOSO]}\n")
    salida.write(f"push-visto: {por_veredicto[VEREDICTO_PUSH]}\n")
    salida.write(f"fallas: {por_veredicto[VEREDICTO_FALLA]}\n")
    for (veredicto, regla), n in sorted(cuentas.items()):
        salida.write(f"  {veredicto:<12} {regla:<28} {n}\n")
    salida.write(f"ultimo: {ultimo}\n")
    return 0


# ---------------------------------------------------------------- gancho


def decidir(evento: Mapping[str, Any], entorno: Mapping[str, str]) -> str | None:
    """Motivo del rechazo para un evento ``PreToolUse``; ``None`` si la orden pasa."""
    if evento.get("tool_name") not in (None, "Bash"):
        return None
    entrada = evento.get("tool_input")
    orden = entrada.get("command") if isinstance(entrada, Mapping) else None
    if not isinstance(orden, str) or not orden.strip():
        return None
    cwd = str(evento.get("cwd") or os.getcwd())

    heredoc = evaluar_heredoc(orden)
    if heredoc:
        regla, motivo, ejemplo, nombre = heredoc
        registrar(entorno, VEREDICTO_RECHAZO, f"heredoc:{regla}", nombre)
        return MENSAJE_HEREDOC.format(motivo=motivo, ejemplo=ejemplo)

    veredicto = evaluar_cuenta(orden, cwd, entorno)
    if veredicto is None:
        return None
    registrar(entorno, veredicto.tipo, veredicto.regla, veredicto.ejecutable)
    if veredicto.tipo == VEREDICTO_RECHAZO:
        return MENSAJE_CUENTA.format(motivo=veredicto.motivo)
    return None


def _escribir(flujo: Any, texto: str) -> None:
    flujo.buffer.write(texto.encode("utf-8"))
    flujo.flush()


def main(argv: Sequence[str] | None = None) -> int:
    entorno = dict(os.environ)
    if "--contar" in (sys.argv[1:] if argv is None else argv):
        return contar(entorno, sys.stdout)

    resultado: list[tuple[str | None, str]] = []

    def trabajar() -> None:
        try:
            # ``utf-8-sig`` acepta una entrada con BOM.
            texto = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
            evento = json.loads(texto)
            if not isinstance(evento, dict):
                raise TypeError("entrada que no es un objeto JSON")
            resultado.append((decidir(evento, entorno), ""))
        except Exception as error:
            nombre = type(error).__name__
            registrar(entorno, VEREDICTO_FALLA, nombre)
            resultado.append(
                (None, f"guarda previa: no pude leer o decidir ({nombre}); dejo pasar la orden.")
            )

    hilo = threading.Thread(target=trabajar, daemon=True)
    hilo.start()
    hilo.join(TOPE_SEGUNDOS)
    motivo: str | None = None
    aviso = ""
    if hilo.is_alive():
        registrar(entorno, VEREDICTO_FALLA, "tope")
        aviso = f"guarda previa: paso de {TOPE_SEGUNDOS:g} s; dejo pasar la orden."
    elif resultado:
        motivo, aviso = resultado[0]
    else:
        aviso = "guarda previa: fallo; dejo pasar la orden."
    try:
        if motivo:
            decision = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": motivo,
                }
            }
            _escribir(sys.stdout, json.dumps(decision) + "\n")
        elif aviso:
            _escribir(sys.stdout, json.dumps({"systemMessage": aviso}) + "\n")
    except Exception:
        pass
    os._exit(0)  # un hilo atascado no debe retener el proceso; este gancho nunca sale con 2


if __name__ == "__main__":
    sys.exit(main())
