"""Pruebas de ``scripts/guarda_previa.py`` (issue #186): el gancho ``PreToolUse`` se prueba por subproceso.

Las órdenes de rechazo reproducen, parafraseadas, los pasos fallidos por heredoc de ``learning/episodes/``
(los episodios guardan la causa, no la orden literal). Los casos «legítimas» y «se escapaban» salen de la
revisión del PR #191. No hay red: la cuenta activa sale de un ``hosts.yml`` falso. La entrada y la salida
del gancho se pasan como BYTES, como las entrega Claude Code.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts import guarda_previa as gp

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "guarda_previa.py"
TOKEN_LITERAL = "tok_literal_ABC123XYZ"

HOSTS_AJENO = (
    "github.com:\n    users:\n        cherrera0001:\n        vinculaterritorio:\n"
    "    git_protocol: https\n    user: vinculaterritorio\n"
)
HOSTS_PROPIO = HOSTS_AJENO.replace("user: vinculaterritorio", "user: cherrera0001")
# El usuario de otro host no es el de github.com.
HOSTS_OTRO_HOST_PROPIO = (
    "github.com:\n    user: vinculaterritorio\nenterprise.example:\n    user: cherrera0001\n"
)
HOSTS_OTRO_HOST_AJENO = (
    "github.com:\n    user: cherrera0001\nenterprise.example:\n    user: vinculaterritorio\n"
)


def _ordenes(*lineas: str) -> str:
    return "\n".join(lineas)


def _relleno(n: int) -> list[str]:
    return [f"linea de texto {i}" for i in range(n)]


# Casos históricos: todos deben rechazarse.
CASOS_HISTORICOS = {
    "002-cuerpos-de-issues": _ordenes(
        "gh issue create --title Epica --body \"$(cat <<'EOF'", *_relleno(70), "EOF", ')"'
    ),
    "007-parche-modulo": _ordenes(
        "python - <<'EOF'",
        "from pathlib import Path",
        "p = Path('src/x.py')",
        "p.write_text(p.read_text())",
        "EOF",
    ),
    "062-parche-rescate-largo": _ordenes(
        ".venv/Scripts/python.exe - <<'PY'", *[f"s = s.replace('a{i}', 'b{i}')" for i in range(80)], "PY"
    ),
    "071-parche-registro-enganches": _ordenes(
        "cd src && python <<'EOF'", *[f"x{i} = {i}" for i in range(75)], "EOF"
    ),
    "069-guion-de-correccion": _ordenes(
        "python - <<'EOF'", "texto = 'a\\nb'", "open('f.py', 'w').write(texto)", "EOF"
    ),
    "054-sustituciones-con-asercion": _ordenes(
        "python3 - <<EOF", "t = open('scripts/devlog.py').read()", "assert 'x' in t", "EOF"
    ),
    "027-arreglo-de-tests": _ordenes(
        "python - <<'EOF'", "import re", "re.sub('a', 'b', 'c')", "EOF", "ruff check ."
    ),
    "067-test-con-barra-invertida": _ordenes(
        "cat > tests/test_rescate.py <<'EOF'", "def test_x():", "    assert 'a\\\\b' == 'a\\\\b'", "EOF"
    ),
    "011-parche-con-salto": _ordenes("python - <<'EOF'", "s = 'x\\ny'", "EOF"),
    "012-parche-graph": _ordenes("python - <<'EOF'", "print('graph.py')", "EOF"),
    "080-pruebas-nuevas": _ordenes("python - <<'EOF'", "pruebas = 'def test_a():\\n    pass'", "EOF"),
}

# Heredocs con un intérprete real que se escapaban (revisión del PR #191) y otros de riesgo.
SE_ESCAPABAN = {
    "ruta_citada_con_espacios": _ordenes(
        '"/f/Code/Agents Learning Loops/.venv/Scripts/python" - <<EOF', "print(1)", "EOF"
    ),
    "python3_12": _ordenes("python3.12 - <<'EOF'", "print(1)", "EOF"),
    "ipython": _ordenes("ipython <<'EOF'", "print(1)", "EOF"),
    "delimitador_numerico": _ordenes("python - <<1", "print(1)", "1"),
    "continuacion": _ordenes("python \\", "  - <<'EOF'", "print(1)", "EOF"),
    "guion_menos": _ordenes("python - <<-EOF", "\tprint(1)", "\tEOF"),
    "delimitador_entre_comillas": _ordenes('python - << "EOF"', "print(1)", "EOF"),
    "asignacion_de_entorno": _ordenes("PYTHONPATH=src python - <<'EOF'", "print(1)", "EOF"),
    "uv_run_python": _ordenes("uv run python - <<'EOF'", "print(1)", "EOF"),
    "sin_cierre_citado": _ordenes("python - <<'EOF'", "print(1)"),
    "sin_cierre_mayusculas": _ordenes("python <<EOF", "print(1)"),
    "tras_otra_orden": _ordenes("ls && python - <<'EOF'", "print(1)", "EOF"),
    "bash": _ordenes("bash <<EOF", "ls", "EOF"),
    "node": _ordenes("node - <<'JS'", "console.log(1)", "JS"),
    "cat_a_python": _ordenes("cat <<'EOF' | python -", "print(1)", "EOF"),
    "tee_fuente": _ordenes("tee scripts/nuevo.sh <<'EOF'", "echo hola", "EOF"),
    "ruta_windows": _ordenes('"C:\\Users\\yo\\venv\\Scripts\\python.exe" - <<EOF', "print(1)", "EOF"),
}

LEGITIMAS = {
    "commit_tras_pytest": _ordenes(
        ".venv/Scripts/python -m pytest -q && git commit -m \"$(cat <<'EOF'",
        "fix: corrige el redondeo",
        "",
        "EOF",
        ')"',
    ),
    "pr_tras_ruff": _ordenes(
        "python -m ruff check . && gh pr create --title t --body \"$(cat <<'EOF'", "Closes #1", "EOF", ')"'
    ),
    "commit_con_heredoc": _ordenes(
        "git commit -m \"$(cat <<'EOF'", "fix: corrige el redondeo", "", "Closes #1", "EOF", ')"'
    ),
    "datos_cortos": _ordenes("cat > datos.txt <<'EOF'", "uno", "dos", "tres", "EOF"),
    "redireccion_detras": _ordenes("cat <<'EOF' > notas.md", "# Notas", "texto", "EOF"),
    "json_corto": _ordenes("cat > learning/episodes/083.json <<'EOF'", '{"seq": 83}', "EOF"),
    "python_antes_en_otra_orden": _ordenes("python --version; cat > a.txt <<EOF", "hola", "EOF"),
    "palabra_python_en_echo": _ordenes("echo python; cat > notas.txt <<EOF", "hola", "EOF"),
    "desplazamiento_en_python_c": 'python -c "print(1 << 3)"',
    "desplazamiento_sin_espacios": 'python -c "x = 1<<n; print(x)"',
    "cadena_con_menor_menor": 'echo "uso: cmd <<EOF para un heredoc"',
    "grep_de_menor_menor": "grep -n '<<' scripts/guarda_previa.py",
    "cadena_aqui": 'grep foo <<< "texto de prueba"',
    "python_multilinea_sin_heredoc": _ordenes('python -c "', "n = 3", "print(1 << n)", '"'),
    "palabra_python_en_mensaje": _ordenes(
        "git commit -m \"usa python en el CI\" -F - <<'EOF'", "cuerpo corto", "EOF"
    ),
    "pytest": "python -m pytest tests -q",
    "lectura_gh": "gh pr view 5 --json state",
    "heredoc_de_60_lineas": _ordenes("cat > lista.txt <<'EOF'", *_relleno(60), "EOF"),
}


def _evento(orden: str, cwd: Path | str, herramienta: str = "Bash") -> bytes:
    carga = {"tool_name": herramienta, "tool_input": {"command": orden}, "cwd": str(cwd)}
    return json.dumps(carga, ensure_ascii=False).encode("utf-8")


def _entorno(tmp_path: Path, hosts: str = HOSTS_PROPIO, **extra: str) -> dict[str, str]:
    config = tmp_path / "ghconfig"
    config.mkdir(exist_ok=True)
    (config / "hosts.yml").write_text(hosts, encoding="utf-8")
    entorno = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "GH_CONFIG_DIR": str(config),
        "GUARDA_PREVIA_REGISTRO": str(tmp_path / "registro.jsonl"),
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
    }
    entorno.update(extra)
    return entorno


def _gancho(entrada: bytes, entorno: dict[str, str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=entrada,
        capture_output=True,
        env=entorno,
        timeout=30,
        check=False,
    )


def _motivo(proc: subprocess.CompletedProcess[bytes]) -> str | None:
    """Motivo del rechazo que el gancho escribió por stdout, o ``None`` si dejó pasar la orden."""
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None
    datos = json.loads(proc.stdout.decode("utf-8"))
    if "hookSpecificOutput" not in datos:
        return None
    salida = datos["hookSpecificOutput"]
    assert salida["hookEventName"] == "PreToolUse"
    assert salida["permissionDecision"] == "deny"
    return str(salida["permissionDecisionReason"])


def _registro(tmp_path: Path) -> list[dict[str, str]]:
    ruta = tmp_path / "registro.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]


def _repo(carpeta: Path, remoto: str) -> Path:
    carpeta.mkdir()
    subprocess.run(["git", "init", "-q", str(carpeta)], check=True)
    subprocess.run(["git", "-C", str(carpeta), "remote", "add", "origin", remoto], check=True)
    return carpeta


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _repo(tmp_path / "repo", "https://github.com/cherrera0001/Agents_Learning_Loops.git")


@pytest.fixture
def otro_repo(tmp_path: Path) -> Path:
    return _repo(tmp_path / "otro", "git@github.com:vinculaterritorio/VT.git")


# ---------------------------------------------------------------- heredoc


@pytest.mark.parametrize("caso", sorted(CASOS_HISTORICOS))
def test_los_casos_historicos_se_rechazan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(CASOS_HISTORICOS[caso], tmp_path), _entorno(tmp_path))
    motivo = _motivo(proc)
    assert motivo is not None
    assert "herramienta de edición" in motivo
    assert _registro(tmp_path)[0]["veredicto"] == "rechazo"


def test_son_los_once_casos_historicos() -> None:
    assert len(CASOS_HISTORICOS) == 11


@pytest.mark.parametrize("caso", sorted(SE_ESCAPABAN))
def test_los_heredocs_con_interprete_real_se_rechazan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(SE_ESCAPABAN[caso], tmp_path), _entorno(tmp_path))
    assert _motivo(proc) is not None, caso


@pytest.mark.parametrize("caso", sorted(LEGITIMAS))
def test_las_ordenes_legitimas_pasan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(LEGITIMAS[caso], tmp_path), _entorno(tmp_path))
    assert _motivo(proc) is None, caso
    assert proc.stdout.strip() == b""
    # Fuera de un repositorio, un `gh pr create` solo puede quedar como «dudoso».
    assert [x for x in _registro(tmp_path) if x["veredicto"] == "rechazo"] == []


def test_un_heredoc_de_61_lineas_se_rechaza_por_largo_y_el_mensaje_distingue_el_destino(
    tmp_path: Path,
) -> None:
    entorno = _entorno(tmp_path)
    suelto = _motivo(
        _gancho(_evento(_ordenes("cat > lista.txt <<'EOF'", *_relleno(61), "EOF"), tmp_path), entorno)
    )
    commit = _motivo(
        _gancho(
            _evento(_ordenes("git commit -m \"$(cat <<'EOF'", *_relleno(61), "EOF", ')"'), tmp_path), entorno
        )
    )
    cuerpo = _motivo(
        _gancho(
            _evento(_ordenes("gh pr create --body \"$(cat <<'EOF'", *_relleno(61), "EOF", ')"'), tmp_path),
            entorno,
        )
    )
    assert suelto is not None
    assert commit is not None
    assert cuerpo is not None
    assert "git commit -F archivo.txt" in commit
    assert "--body-file" in cuerpo
    assert "--body-file" not in commit
    assert [x["regla"] for x in _registro(tmp_path)] == ["heredoc:largo"] * 3


def test_el_mensaje_de_rechazo_dice_que_hacer_en_su_lugar(tmp_path: Path) -> None:
    motivo = _motivo(_gancho(_evento(CASOS_HISTORICOS["012-parche-graph"], tmp_path), _entorno(tmp_path)))
    assert motivo is not None
    assert "Write o Edit" in motivo
    assert "ejecútalo" in motivo
    assert "PowerShell" in motivo


def test_otras_herramientas_y_entradas_vacias_pasan(tmp_path: Path) -> None:
    entorno = _entorno(tmp_path)
    peligrosa = CASOS_HISTORICOS["012-parche-graph"]
    assert _motivo(_gancho(_evento(peligrosa, tmp_path, herramienta="PowerShell"), entorno)) is None
    assert _motivo(_gancho(_evento(peligrosa, tmp_path, herramienta="Edit"), entorno)) is None
    assert _motivo(_gancho(json.dumps({"tool_name": "Bash", "tool_input": {}}).encode(), entorno)) is None
    assert _motivo(_gancho(b"", entorno)) is None
    assert _motivo(_gancho(_evento("", tmp_path), entorno)) is None


# ---------------------------------------------------------------- cuenta


def test_el_incidente_original_se_rechaza_con_texto_en_castellano_por_bytes(
    tmp_path: Path, repo: Path
) -> None:
    for texto in ('"Ámbito del cambio"', '"Í”“ ñ — €"', "'Ámbito'"):
        orden = f"gh pr comment 185 --body {texto}"
        proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
        motivo = _motivo(proc)
        assert motivo is not None, texto
        assert "vinculaterritorio" in motivo
        assert 'GH_TOKEN="$(gh auth token --user cherrera0001)" gh' in motivo
        proc.stdout.decode("ascii")  # la decisión sale en ASCII puro (JSON con escapes)
    contenido = (tmp_path / "registro.jsonl").read_bytes().decode("utf-8")
    assert "Ámbito" not in contenido


def test_gh_de_escritura_con_la_cuenta_activa_propia_pasa(tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento("gh pr comment 185 --body hola", repo), _entorno(tmp_path, HOSTS_PROPIO))
    assert _motivo(proc) is None
    assert _registro(tmp_path) == []


ESCRITURAS = [
    "gh pr create --title t --body b",
    "gh pr comment 185 --body x",
    "gh pr merge 5 --squash",
    "gh pr edit 5 --title x",
    "gh pr close 5",
    "gh pr reopen 5",
    "gh pr review 5 --approve",
    "gh pr ready 5",
    "gh issue create --title t",
    "gh issue comment 3 --body x",
    "gh issue edit 3 --add-label a",
    "gh issue close 3",
    "gh issue reopen 3",
    "gh issue pin 3",
    "gh issue unpin 3",
    "gh issue delete 3",
    "gh issue transfer 3 otro/repo",
    "gh release create v1",
    "gh release upload v1 a.zip",
    "gh label create nueva",
    "gh project item-add 5 --url u",
    "gh project item-edit --id x",
    "gh project item-delete 5 --id x",
    "gh project item-archive 5 --id x",
    "gh project item-create 5 --title t",
    "gh project field-create 5 --name n",
    "gh project edit 5 --title x",
    "gh project close 5",
    "gh workflow run ci.yml",
    "gh workflow disable ci.yml",
    "gh run cancel 12",
    "gh run rerun 12",
    "gh repo edit --description x",
    "gh repo archive",
    "gh secret set X --body y",
    "gh variable delete X",
    "gh api -X POST repos/cherrera0001/Agents_Learning_Loops/issues/1/comments",
    "gh api --method=DELETE repos/cherrera0001/Agents_Learning_Loops/issues/comments/1",
    "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1 -X PATCH",
    "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1/comments -f body=hola",
    "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1/comments -F body=@a.txt",
    "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1/comments --input a.json",
    "gh api graphql -f query='mutation { addComment { clientMutationId } }'",
    "echo ok; gh pr comment 1 --body x",
    'gh pr comment 1 --body "$(cat nota.md)"',
]


@pytest.mark.parametrize("orden", ESCRITURAS)
def test_cada_escritura_se_frena_con_la_cuenta_activa_ajena(orden: str, tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert _motivo(proc) is not None, orden


LECTURAS_Y_DUDOSAS = [
    # lecturas
    "gh pr view 5",
    "gh pr list --state open",
    "gh pr checks 5",
    "gh issue list",
    "gh issue view 3 --comments",
    "gh project item-list 5 --owner cherrera0001",
    "gh project list --owner cherrera0001",
    "gh run view 12",
    "gh run list",
    "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1",
    "gh api -X GET repos/cherrera0001/Agents_Learning_Loops/issues -f state=open",
    "gh api graphql -f query='query { viewer { login } }'",
    "gh release list",
    "git status",
    "git log --oneline",
    "echo gh pr merge",
    "gh auth status",
    # otro repositorio
    "gh pr comment 1 --body x -R vinculaterritorio/VT",
    "gh --repo vinculaterritorio/VT pr comment 1 --body x",
    "gh api repos/otro/repo/issues/1/comments -f body=x",
    # el token se fija de cualquier forma
    'GH_TOKEN="$(gh auth token --user cherrera0001)" gh pr comment 1 --body x',
    'export GH_TOKEN="$(gh auth token --user cherrera0001)" && gh pr comment 1 --body x',
    'export GH_TOKEN="$(gh auth token --user cherrera0001)"; gh pr comment 1 --body x',
    'export GH_TOKEN="$(gh auth token --user cherrera0001)"\ngh pr comment 1 --body x',
    "export GH_TOKEN=$(gh auth token --user cherrera0001) && gh pr comment 1 --body x",
    "GH_TOKEN=$(gh auth token --user cherrera0001) gh pr comment 1 --body x",
    "env GH_TOKEN=$(gh auth token --user cherrera0001) gh pr comment 1 --body x",
    # cambia de directorio: dudoso
    "cd ../otro && gh pr comment 1 --body x",
    "git -C ../otro push",
]


@pytest.mark.parametrize("orden", LECTURAS_Y_DUDOSAS)
def test_las_lecturas_y_lo_dudoso_no_se_frenan(orden: str, tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert _motivo(proc) is None, orden


def test_git_push_nunca_se_rechaza_y_se_cuenta_como_push_visto(tmp_path: Path, repo: Path) -> None:
    entorno = _entorno(tmp_path, HOSTS_AJENO)
    ordenes = [
        "git push origin rama",
        "git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin rama",
        "cd subcarpeta && git push",
        'GH_TOKEN="$(gh auth token --user vinculaterritorio)" git push',
    ]
    for orden in ordenes:
        assert _motivo(_gancho(_evento(orden, repo), entorno)) is None, orden
    registro = _registro(tmp_path)
    assert [x["veredicto"] for x in registro] == ["push-visto"] * len(ordenes)


def test_en_otro_repositorio_no_se_frena_ni_se_cuenta(tmp_path: Path, otro_repo: Path) -> None:
    proc = _gancho(_evento("gh pr comment 1 --body x", otro_repo), _entorno(tmp_path, HOSTS_AJENO))
    assert _motivo(proc) is None
    assert _registro(tmp_path) == []


def test_token_de_otra_cuenta_en_la_orden_se_rechaza_aunque_la_activa_sea_propia(
    tmp_path: Path, repo: Path
) -> None:
    for orden in (
        'GH_TOKEN="$(gh auth token --user vinculaterritorio)" gh pr comment 1 --body x',
        'export GH_TOKEN="$(gh auth token --user vinculaterritorio)" && gh pr comment 1 --body x',
    ):
        motivo = _motivo(_gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_PROPIO)))
        assert motivo is not None, orden
        assert "vinculaterritorio" in motivo


def test_token_literal_pasa_se_cuenta_como_dudoso_y_no_se_imprime(tmp_path: Path, repo: Path) -> None:
    orden = f"GH_TOKEN={TOKEN_LITERAL} gh pr comment 1 --body x"
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert _motivo(proc) is None
    registro = (tmp_path / "registro.jsonl").read_text(encoding="utf-8")
    assert json.loads(registro)["veredicto"] == "pasa-dudoso"
    for texto in (proc.stdout.decode(), proc.stderr.decode(), registro):
        assert TOKEN_LITERAL not in texto


def test_token_en_el_entorno_del_gancho_pasa_y_se_cuenta_como_dudoso(tmp_path: Path, repo: Path) -> None:
    proc = _gancho(
        _evento("gh pr comment 1 --body x", repo), _entorno(tmp_path, HOSTS_AJENO, GH_TOKEN=TOKEN_LITERAL)
    )
    assert _motivo(proc) is None
    assert TOKEN_LITERAL not in proc.stdout.decode() + (tmp_path / "registro.jsonl").read_text(
        encoding="utf-8"
    )
    assert _registro(tmp_path)[0]["regla"] == "cuenta:token_en_entorno"


def test_la_cuenta_activa_es_la_de_github_com_y_no_la_de_otro_host(tmp_path: Path, repo: Path) -> None:
    orden = "gh pr comment 1 --body x"
    assert _motivo(_gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_OTRO_HOST_PROPIO))) is not None
    assert _motivo(_gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_OTRO_HOST_AJENO))) is None


def test_si_no_se_puede_saber_la_cuenta_deja_pasar_y_lo_cuenta(tmp_path: Path, repo: Path) -> None:
    entorno = _entorno(tmp_path)
    (tmp_path / "ghconfig" / "hosts.yml").unlink()
    entorno["USERPROFILE"] = entorno["HOME"] = str(tmp_path / "vacio")
    proc = _gancho(_evento("gh pr comment 1 --body x", repo), entorno)
    assert _motivo(proc) is None
    assert _registro(tmp_path)[0]["veredicto"] == "pasa-dudoso"


# ---------------------------------------------------------------- seguridad del gancho y registro


def test_entrada_rota_sale_con_0_sin_decision_y_se_cuenta(tmp_path: Path) -> None:
    for entrada in (b"esto no es json", b"\xff\xfe\x00 roto", b"[1, 2]", b"null"):
        proc = _gancho(entrada, _entorno(tmp_path))
        assert proc.returncode == 0
        assert _motivo(proc) is None


def test_si_decidir_lanza_una_excepcion_sale_con_0_sin_decision(tmp_path: Path) -> None:
    codigo = (
        "import scripts.guarda_previa as g\n"
        "def roto(e, n):\n    raise RuntimeError('x')\n"
        "g.decidir = roto\ng.main([])\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", codigo],
        input=_evento("ls", tmp_path),
        capture_output=True,
        env={**_entorno(tmp_path), "PYTHONPATH": str(RAIZ)},
        cwd=RAIZ,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert _motivo(proc) is None
    assert _registro(tmp_path)[0] == {**_registro(tmp_path)[0], "veredicto": "falla", "regla": "RuntimeError"}


def test_si_pasa_del_tope_sale_con_0_sin_decision(tmp_path: Path) -> None:
    codigo = (
        "import time, scripts.guarda_previa as g\n"
        "g.TOPE_SEGUNDOS = 0.3\n"
        "g.decidir = lambda e, n: (time.sleep(10), 'x')[1]\n"
        "g.main([])\n"
    )
    inicio = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", codigo],
        input=_evento("ls", tmp_path),
        capture_output=True,
        env={**_entorno(tmp_path), "PYTHONPATH": str(RAIZ)},
        cwd=RAIZ,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "deny" not in proc.stdout.decode()
    assert time.monotonic() - inicio < 8
    assert _registro(tmp_path)[0]["regla"] == "tope"


def _bash() -> str | None:
    git = shutil.which("git")
    if git:
        candidata = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if candidata.is_file():
            return str(candidata)
    return shutil.which("bash")


def _comando_del_gancho() -> str:
    ajustes = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    ganchos = ajustes["hooks"]["PreToolUse"]
    assert ganchos[0]["matcher"] == "Bash"
    assert "SessionStart" in ajustes["hooks"]
    comando = ganchos[0]["hooks"][0]
    assert comando["timeout"] > gp.TOPE_SEGUNDOS
    return str(comando["command"])


def test_la_orden_registrada_no_puede_devolver_2(tmp_path: Path) -> None:
    comando = _comando_del_gancho()
    assert "guarda_previa.py" in comando
    assert comando.rstrip().endswith("|| true")
    bash = _bash()
    if bash is None:
        pytest.skip("no hay bash para ejecutar la orden del gancho")
    # 1. El guion no existe (una rama anterior).
    vacio = tmp_path / "sin_guion"
    vacio.mkdir()
    # 2. El guion lanza una excepción al importarse.
    roto = tmp_path / "roto"
    (roto / "scripts").mkdir(parents=True)
    (roto / "scripts" / "guarda_previa.py").write_text(
        "raise RuntimeError('importacion')\n", encoding="utf-8"
    )
    # 3. La ruta del proyecto no existe.
    for carpeta in (vacio, roto, tmp_path / "no_existe"):
        proc = subprocess.run(
            [bash, "-c", comando],
            input=_evento("ls", tmp_path),
            capture_output=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": carpeta.as_posix()},
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, (carpeta, proc.stderr)


def test_el_contador_suma_los_veredictos_y_una_orden_lo_lee(tmp_path: Path, repo: Path) -> None:
    entorno = _entorno(tmp_path, HOSTS_AJENO)
    _gancho(_evento(CASOS_HISTORICOS["012-parche-graph"], tmp_path), entorno)
    _gancho(_evento(CASOS_HISTORICOS["011-parche-con-salto"], tmp_path), entorno)
    _gancho(_evento("gh pr comment 1 --body Ámbito", repo), entorno)
    _gancho(_evento("git push", repo), entorno)
    _gancho(_evento("cd .. && gh pr comment 1 --body x", repo), entorno)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--contar"], capture_output=True, env=entorno, timeout=30, check=False
    )
    salida = proc.stdout.decode("utf-8")
    assert proc.returncode == 0
    assert "rechazos: 3" in salida
    assert "pasa-dudoso: 1" in salida
    assert "push-visto: 1" in salida
    assert "heredoc:interprete" in salida
    assert "cuenta:cuenta_activa" in salida


def test_contar_sin_registro_lo_dice(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--contar"],
        capture_output=True,
        env=_entorno(tmp_path),
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert b"Sin registro" in proc.stdout


def test_el_registro_no_guarda_texto_de_la_orden(tmp_path: Path) -> None:
    orden = _ordenes(
        f"KAGGLE_KEY=valor123 GH_TOKEN={TOKEN_LITERAL} python - <<'EOF'",
        "print('segunda linea secreta')",
        "EOF",
    )
    _gancho(_evento(orden, tmp_path), _entorno(tmp_path))
    texto = (tmp_path / "registro.jsonl").read_text(encoding="utf-8")
    for prohibido in ("valor123", "KAGGLE", TOKEN_LITERAL, "segunda linea", "print("):
        assert prohibido not in texto
    ficha = json.loads(texto)
    assert set(ficha) == {"ts", "regla", "veredicto", "ejecutable"}
    assert ficha["ejecutable"] == "python"


def test_el_registro_esta_ignorado_por_git() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".claude/guarda_previa.jsonl"],
        cwd=RAIZ,
        check=False,
        capture_output=True,
    )
    assert proc.returncode == 0


def test_el_tiempo_por_orden_cabe_en_el_tope(tmp_path: Path) -> None:
    entorno = _entorno(tmp_path)
    inicio = time.monotonic()
    _gancho(_evento(LEGITIMAS["commit_con_heredoc"], tmp_path), entorno)
    assert time.monotonic() - inicio < gp.TOPE_SEGUNDOS
