"""Pruebas de ``scripts/guarda_previa.py`` (issue #186): el gancho ``PreToolUse`` se prueba por subproceso.

Las órdenes de rechazo reproducen, parafraseadas, los pasos fallidos por heredoc de ``learning/episodes/``
(los episodios guardan la causa, no la orden literal). No hay red: la cuenta activa sale de un
``hosts.yml`` falso y el token propio de una variable de prueba.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import guarda_previa as gp

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "guarda_previa.py"
TOKEN_PROPIO = "tok_propio_ABC123XYZ"
TOKEN_AJENO = "tok_ajeno_QQQ987"

HOSTS_AJENO = (
    "github.com:\n    users:\n        cherrera0001:\n        vinculaterritorio:\n"
    "    git_protocol: https\n    user: vinculaterritorio\n"
)
HOSTS_PROPIO = HOSTS_AJENO.replace("user: vinculaterritorio", "user: cherrera0001")


def _ordenes(*lineas: str) -> str:
    return "\n".join(lineas)


def _relleno(n: int) -> list[str]:
    return [f"linea de texto {i}" for i in range(n)]


# Casos históricos: (episodio, orden parafraseada). Todos deben rechazarse.
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

OTROS_RECHAZOS = {
    "bash": _ordenes("bash <<EOF", "ls", "EOF"),
    "node": _ordenes("node - <<'JS'", "console.log(1)", "JS"),
    "cat_a_python": _ordenes("cat <<'EOF' | python -", "print(1)", "EOF"),
    "tee_fuente": _ordenes("tee scripts/nuevo.sh <<'EOF'", "echo hola", "EOF"),
}

LEGITIMAS = {
    "commit_con_heredoc": _ordenes(
        "git commit -m \"$(cat <<'EOF'", "fix: corrige el redondeo", "", "Closes #1", "EOF", ')"'
    ),
    "datos_cortos": _ordenes("cat > datos.txt <<'EOF'", "uno", "dos", "tres", "EOF"),
    "redireccion_detras": _ordenes("cat <<'EOF' > notas.md", "# Notas", "texto", "EOF"),
    "json_corto": _ordenes("cat > learning/episodes/083.json <<'EOF'", '{"seq": 83}', "EOF"),
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


def _evento(orden: str, cwd: Path | str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": orden}, "cwd": str(cwd)})


def _entorno(tmp_path: Path, hosts: str = HOSTS_PROPIO, **extra: str) -> dict[str, str]:
    config = tmp_path / "ghconfig"
    config.mkdir(exist_ok=True)
    (config / "hosts.yml").write_text(hosts, encoding="utf-8")
    entorno = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
        "GH_CONFIG_DIR": str(config),
        "GUARDA_PREVIA_TOKEN_PROPIO": TOKEN_PROPIO,
        "GUARDA_PREVIA_REGISTRO": str(tmp_path / "registro.jsonl"),
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
    }
    entorno.update(extra)
    return entorno


def _gancho(entrada: str, entorno: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=entrada,
        capture_output=True,
        text=True,
        env=entorno,
        timeout=30,
        check=False,
    )


def _registro(tmp_path: Path) -> list[dict[str, str]]:
    ruta = tmp_path / "registro.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    carpeta = tmp_path / "repo"
    carpeta.mkdir()
    subprocess.run(["git", "init", "-q", str(carpeta)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(carpeta),
            "remote",
            "add",
            "origin",
            "https://github.com/cherrera0001/Agents_Learning_Loops.git",
        ],
        check=True,
    )
    return carpeta


@pytest.fixture
def otro_repo(tmp_path: Path) -> Path:
    carpeta = tmp_path / "otro"
    carpeta.mkdir()
    subprocess.run(["git", "init", "-q", str(carpeta)], check=True)
    subprocess.run(
        ["git", "-C", str(carpeta), "remote", "add", "origin", "git@github.com:vinculaterritorio/VT.git"],
        check=True,
    )
    return carpeta


# ---------------------------------------------------------------- heredoc


@pytest.mark.parametrize("caso", sorted(CASOS_HISTORICOS))
def test_los_casos_historicos_se_rechazan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(CASOS_HISTORICOS[caso], tmp_path), _entorno(tmp_path))
    assert proc.returncode == 2, proc.stderr
    assert "herramienta de edición" in proc.stderr
    assert _registro(tmp_path)[0]["tipo"] == "rechazo"


def test_son_los_once_casos_historicos() -> None:
    assert len(CASOS_HISTORICOS) == 11


@pytest.mark.parametrize("caso", sorted(OTROS_RECHAZOS))
def test_otros_heredocs_de_riesgo_se_rechazan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(OTROS_RECHAZOS[caso], tmp_path), _entorno(tmp_path))
    assert proc.returncode == 2, proc.stderr


@pytest.mark.parametrize("caso", sorted(LEGITIMAS))
def test_las_ordenes_legitimas_pasan(caso: str, tmp_path: Path) -> None:
    proc = _gancho(_evento(LEGITIMAS[caso], tmp_path), _entorno(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert _registro(tmp_path) == []


def test_son_al_menos_diez_legitimas() -> None:
    assert len(LEGITIMAS) >= 10


def test_un_heredoc_de_texto_de_61_lineas_se_rechaza_por_largo(tmp_path: Path) -> None:
    orden = _ordenes("cat > lista.txt <<'EOF'", *_relleno(61), "EOF")
    proc = _gancho(_evento(orden, tmp_path), _entorno(tmp_path))
    assert proc.returncode == 2
    assert _registro(tmp_path)[0]["regla"] == "heredoc:largo"


def test_el_mensaje_de_rechazo_dice_que_hacer_en_su_lugar(tmp_path: Path) -> None:
    proc = _gancho(_evento(CASOS_HISTORICOS["012-parche-graph"], tmp_path), _entorno(tmp_path))
    assert "Write o Edit" in proc.stderr
    assert "ejecútalo" in proc.stderr


def test_otras_herramientas_y_entradas_vacias_pasan(tmp_path: Path) -> None:
    entorno = _entorno(tmp_path)
    assert _gancho(json.dumps({"tool_name": "Edit", "tool_input": {}}), entorno).returncode == 0
    assert _gancho("", entorno).returncode == 0
    assert _gancho(json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}}), entorno).returncode == 0


# ---------------------------------------------------------------- cuenta


def test_gh_de_escritura_con_la_cuenta_activa_ajena_se_rechaza(tmp_path: Path, repo: Path) -> None:
    entorno = _entorno(tmp_path, HOSTS_AJENO)
    proc = _gancho(_evento("gh pr comment 185 --body hola", repo), entorno)
    assert proc.returncode == 2
    assert "vinculaterritorio" in proc.stderr
    assert 'GH_TOKEN="$(gh auth token --user cherrera0001)" gh' in proc.stderr
    assert _registro(tmp_path)[0]["regla"] == "cuenta:cuenta_activa"


def test_gh_de_escritura_con_la_cuenta_activa_propia_pasa(tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento("gh pr comment 185 --body hola", repo), _entorno(tmp_path, HOSTS_PROPIO))
    assert proc.returncode == 0


@pytest.mark.parametrize(
    "orden",
    [
        "gh pr create --title t --body b",
        "gh pr merge 5 --squash",
        "gh pr edit 5 --title x",
        "gh pr close 5",
        "gh pr review 5 --approve",
        "gh issue create --title t",
        "gh issue comment 3 --body x",
        "gh issue edit 3 --add-label a",
        "gh issue close 3",
        "gh api -X POST repos/cherrera0001/Agents_Learning_Loops/issues/1/comments",
        "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1 -X PATCH",
        "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1/comments -f body=hola",
        "gh project item-edit --id x",
        "gh release create v1",
        "git push origin rama",
        "git -c credential.helper= push origin rama",
        "cd subcarpeta && git push",
    ],
)
def test_cada_escritura_se_frena_con_la_cuenta_ajena(orden: str, tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert proc.returncode == 2, orden


@pytest.mark.parametrize(
    "orden",
    [
        "gh pr view 5",
        "gh pr list --state open",
        "gh issue list",
        "gh issue view 3 --comments",
        "gh api repos/cherrera0001/Agents_Learning_Loops/issues/1",
        "gh api -X GET repos/cherrera0001/Agents_Learning_Loops/issues -f state=open",
        "gh api graphql -f query='query { viewer { login } }'",
        "gh release list",
        "gh pr comment 1 --body x -R vinculaterritorio/VT",
        "git status",
        "git log --oneline",
        "echo gh pr merge",
    ],
)
def test_las_lecturas_y_otros_repositorios_no_se_frenan(orden: str, tmp_path: Path, repo: Path) -> None:
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert proc.returncode == 0, orden


def test_en_otro_repositorio_no_se_frena(tmp_path: Path, otro_repo: Path) -> None:
    proc = _gancho(_evento("gh pr comment 1 --body x", otro_repo), _entorno(tmp_path, HOSTS_AJENO))
    assert proc.returncode == 0


def test_token_declarado_en_la_orden_de_la_cuenta_propia_pasa(tmp_path: Path, repo: Path) -> None:
    orden = 'GH_TOKEN="$(gh auth token --user cherrera0001)" gh pr comment 1 --body x'
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert proc.returncode == 0, proc.stderr


def test_token_declarado_en_la_orden_de_otra_cuenta_se_rechaza(tmp_path: Path, repo: Path) -> None:
    orden = 'GH_TOKEN="$(gh auth token --user vinculaterritorio)" gh pr comment 1 --body x'
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_PROPIO))
    assert proc.returncode == 2
    assert "vinculaterritorio" in proc.stderr


def test_token_literal_ajeno_se_rechaza_y_no_se_imprime(tmp_path: Path, repo: Path) -> None:
    orden = f"GH_TOKEN={TOKEN_AJENO} gh pr comment 1 --body x"
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_PROPIO))
    assert proc.returncode == 2
    for texto in (proc.stdout, proc.stderr, (tmp_path / "registro.jsonl").read_text(encoding="utf-8")):
        assert TOKEN_AJENO not in texto
        assert TOKEN_PROPIO not in texto


def test_token_literal_propio_pasa_y_no_se_imprime(tmp_path: Path, repo: Path) -> None:
    orden = f"GH_TOKEN={TOKEN_PROPIO} gh pr comment 1 --body x"
    proc = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO))
    assert proc.returncode == 0
    assert TOKEN_PROPIO not in proc.stdout + proc.stderr


def test_token_en_el_entorno_se_compara_con_el_propio(tmp_path: Path, repo: Path) -> None:
    orden = "gh pr comment 1 --body x"
    ajeno = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_PROPIO, GH_TOKEN=TOKEN_AJENO))
    propio = _gancho(_evento(orden, repo), _entorno(tmp_path, HOSTS_AJENO, GH_TOKEN=TOKEN_PROPIO))
    assert ajeno.returncode == 2
    assert propio.returncode == 0
    assert TOKEN_AJENO not in ajeno.stdout + ajeno.stderr


def test_si_no_se_puede_saber_la_cuenta_deja_pasar_y_lo_cuenta(tmp_path: Path, repo: Path) -> None:
    entorno = _entorno(tmp_path)
    (tmp_path / "ghconfig" / "hosts.yml").unlink()
    proc = _gancho(_evento("gh pr comment 1 --body x", repo), entorno)
    assert proc.returncode == 0
    assert "dejo pasar" in proc.stderr
    assert _registro(tmp_path)[0]["tipo"] == "dudoso"


# ---------------------------------------------------------------- seguridad del gancho y registro


def test_si_el_guion_falla_deja_pasar_y_lo_dice(tmp_path: Path) -> None:
    proc = _gancho("esto no es json", _entorno(tmp_path))
    assert proc.returncode == 0
    assert "falló" in proc.stderr
    assert json.loads(proc.stdout)["systemMessage"].startswith("guarda previa")
    assert _registro(tmp_path)[0]["tipo"] == "falla"


def test_si_pasa_del_tope_deja_pasar_y_lo_dice(tmp_path: Path) -> None:
    codigo = (
        "import time, scripts.guarda_previa as g\n"
        "g.TOPE_SEGUNDOS = 0.3\n"
        "g.decidir = lambda e, n: (time.sleep(10), (2, 'x'))[1]\n"
        "g.main([])\n"
    )
    inicio = __import__("time").monotonic()
    proc = subprocess.run(
        [sys.executable, "-c", codigo],
        input=_evento("ls", tmp_path),
        capture_output=True,
        text=True,
        env={**_entorno(tmp_path), "PYTHONPATH": str(RAIZ)},
        cwd=RAIZ,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "dejo pasar" in proc.stderr
    assert __import__("time").monotonic() - inicio < 8
    assert _registro(tmp_path)[0]["regla"] == "tope"


def test_el_tope_declarado_cabe_en_el_del_gancho() -> None:
    ajustes = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    ganchos = ajustes["hooks"]["PreToolUse"]
    assert ganchos[0]["matcher"] == "Bash"
    comando = ganchos[0]["hooks"][0]
    assert "guarda_previa.py" in comando["command"]
    assert comando["timeout"] > gp.TOPE_SEGUNDOS
    assert "SessionStart" in ajustes["hooks"]


def test_el_contador_cuenta_los_rechazos_y_una_orden_lo_lee(tmp_path: Path) -> None:
    entorno = _entorno(tmp_path)
    _gancho(_evento(CASOS_HISTORICOS["012-parche-graph"], tmp_path), entorno)
    _gancho(_evento(CASOS_HISTORICOS["011-parche-con-salto"], tmp_path), entorno)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--contar"],
        capture_output=True,
        text=True,
        env=entorno,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "rechazos: 2" in proc.stdout
    assert "heredoc:interprete" in proc.stdout


def test_contar_sin_registro_lo_dice(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--contar"],
        capture_output=True,
        text=True,
        env=_entorno(tmp_path),
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "Sin registro" in proc.stdout


def test_el_registro_no_guarda_la_orden_entera_ni_secretos(tmp_path: Path) -> None:
    orden = _ordenes(f"GH_TOKEN={TOKEN_AJENO} python - <<'EOF'", "print('segunda linea secreta')", "EOF")
    _gancho(_evento(orden, tmp_path), _entorno(tmp_path))
    texto = (tmp_path / "registro.jsonl").read_text(encoding="utf-8")
    assert TOKEN_AJENO not in texto
    assert "segunda linea" not in texto


def test_el_registro_esta_ignorado_por_git() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", ".claude/guarda_previa.jsonl"],
        cwd=RAIZ,
        check=False,
        capture_output=True,
    )
    assert proc.returncode == 0
