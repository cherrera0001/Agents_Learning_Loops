"""Pruebas unitarias para el empaquetado, verificación y registro de envíos (Issue #106).

Verifica:
1. Empaquetado determinista: dos ejecuciones independientes sobre el mismo directorio
   generan exactamente el mismo archivo ZIP y el mismo hash SHA-256.
2. Exclusión estricta de artefactos temporales y manifiestos de descarga.
3. Validación estructural y detección de adaptadores declarados faltantes o presentes.
4. Operaciones del registro versionado (id incremental, idempotencia por hash, persistencia JSON).
5. Interfaz de línea de comandos (pack, verify, register, list).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts import kaggle_submission
from scripts.kaggle_submission import (
    EXIT_OK,
    SCHEMA_VERSION,
    SubmissionRegistry,
    compute_file_sha256,
    find_declared_adapters,
    main,
    pack_submission,
    validate_submission_dir,
    verify_zip_submission,
)


@pytest.fixture
def dummy_condition_dir(tmp_path: Path) -> Path:
    """Crea una estructura de condición mínima válida para pruebas."""
    cond_dir = tmp_path / "condition_test"
    cond_dir.mkdir()

    # Archivos requeridos
    (cond_dir / "agent.yaml").write_text("model: gemma-4-31b-it\nadapter: null\n", encoding="utf-8")
    (cond_dir / "eval_config.yaml").write_text("timeout: 3600\nmax_tool_calls: 100\n", encoding="utf-8")

    # Archivos recomendados y auxiliares
    configs = cond_dir / "configs"
    configs.mkdir()
    (configs / "sampling.yaml").write_text("temperature: 0.0\ntop_p: 0.95\n", encoding="utf-8")

    prompts = cond_dir / "prompts"
    prompts.mkdir()
    (prompts / "system.md").write_text("Eres un agente desarrollador autónomo.\n", encoding="utf-8")

    # Archivos que deben excluirse al empaquetar
    (cond_dir / "manifest.json").write_text('{"excluded": true}', encoding="utf-8")
    (cond_dir / "download_kit.py").write_text("# script de descarga\n", encoding="utf-8")
    (cond_dir / "README.md").write_text("# Doc local\n", encoding="utf-8")
    pycache = cond_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "temp.pyc").write_bytes(b"\x00\x01\x02")

    return cond_dir


@pytest.fixture
def compiler_ok(monkeypatch):
    """Sustituye el compilador del arnés, que no está en el entorno de pruebas, por uno que aprueba."""
    monkeypatch.setattr(kaggle_submission, "compile_with_adk", lambda _dir: (True, "compilador simulado"))


def test_compile_with_adk_fails_when_the_compiler_is_not_installed(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] in {"adk_submission", "swegemma"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, message = kaggle_submission.compile_with_adk(tmp_path)
    assert ok is False
    assert "NO se compiló" in message


def test_find_declared_adapters() -> None:
    yaml_without_adapter = "model: gemma\nmax_steps: 100\n"
    assert find_declared_adapters(yaml_without_adapter) == []

    yaml_with_null = "model: gemma\nadapter: null\n"
    assert find_declared_adapters(yaml_with_null) == []

    yaml_with_adapter = "model: gemma\nadapter: lora_skills_v1\n"
    assert find_declared_adapters(yaml_with_adapter) == ["lora_skills_v1"]

    yaml_with_quoted = 'model: gemma\nadapter: "lora_placebo"\n'
    assert find_declared_adapters(yaml_with_quoted) == ["lora_placebo"]


@pytest.mark.usefixtures("compiler_ok")
def test_validate_submission_dir_success(dummy_condition_dir: Path) -> None:
    valid, messages = validate_submission_dir(dummy_condition_dir)
    assert valid is True
    assert any("[OK] Archivo presente: agent.yaml" in m for m in messages)
    assert any("[OK] Archivo presente: eval_config.yaml" in m for m in messages)


def test_validate_submission_dir_missing_required(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "agent.yaml").write_text("model: gemma\n", encoding="utf-8")

    valid, messages = validate_submission_dir(incomplete)
    assert valid is False
    assert any("[FALTA] Archivo obligatorio ausente: eval_config.yaml" in m for m in messages)


@pytest.mark.usefixtures("compiler_ok")
def test_validate_submission_dir_adapter_validation(tmp_path: Path) -> None:
    cond_dir = tmp_path / "adapter_test"
    cond_dir.mkdir()
    (cond_dir / "agent.yaml").write_text("model: gemma\nadapter: my_lora\n", encoding="utf-8")
    (cond_dir / "eval_config.yaml").write_text("timeout: 100\n", encoding="utf-8")

    # Sin pesos: debe fallar
    valid, messages = validate_submission_dir(cond_dir)
    assert valid is False
    assert any("my_lora" in m and "ERROR" in m for m in messages)

    # Con pesos presentes: debe pasar
    adapter_dir = cond_dir / "adapters" / "my_lora"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"\x00" * 64)
    (adapter_dir / "adapter_config.json").write_text('{"r": 16}', encoding="utf-8")

    valid_with_weights, messages_weights = validate_submission_dir(cond_dir)
    assert valid_with_weights is True
    assert any("my_lora" in m and "OK" in m for m in messages_weights)


@pytest.mark.usefixtures("compiler_ok")
def test_pack_submission_deterministic(dummy_condition_dir: Path, tmp_path: Path) -> None:
    zip1 = tmp_path / "out1.zip"
    zip2 = tmp_path / "out2.zip"

    sha1, size1 = pack_submission(dummy_condition_dir, zip1)
    sha2, size2 = pack_submission(dummy_condition_dir, zip2)

    assert sha1 == sha2
    assert size1 == size2
    assert zip1.stat().st_size == size1

    # Verificar contenido interno y exclusiones
    with zipfile.ZipFile(zip1, "r") as zf:
        namelist = zf.namelist()
        assert "agent.yaml" in namelist
        assert "eval_config.yaml" in namelist
        assert "configs/sampling.yaml" in namelist
        assert "prompts/system.md" in namelist

        # Exclusiones
        assert "manifest.json" not in namelist
        assert "download_kit.py" not in namelist
        assert "README.md" not in namelist
        assert not any("__pycache__" in name for name in namelist)


@pytest.mark.usefixtures("compiler_ok")
def test_verify_zip_submission(dummy_condition_dir: Path, tmp_path: Path) -> None:
    zip_path = tmp_path / "valid.zip"
    pack_submission(dummy_condition_dir, zip_path)

    valid, messages, sha, size = verify_zip_submission(zip_path)
    assert valid is True
    assert sha == compute_file_sha256(zip_path)
    assert size == zip_path.stat().st_size
    assert any("agent.yaml" in m and "OK" in m for m in messages)


def test_verify_zip_submission_corrupt_or_missing(tmp_path: Path) -> None:
    non_existent = tmp_path / "non_existent.zip"
    valid, _msgs, _, _ = verify_zip_submission(non_existent)
    assert valid is False

    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_text("este no es un zip", encoding="utf-8")
    valid_corrupt, msgs_corrupt, _, _ = verify_zip_submission(corrupt)
    assert valid_corrupt is False
    assert any("no es un ZIP válido" in m for m in msgs_corrupt)


@pytest.mark.usefixtures("compiler_ok")
def test_submission_registry_lifecycle(dummy_condition_dir: Path, tmp_path: Path) -> None:
    registry_file = tmp_path / "submissions" / "registry.json"
    registry = SubmissionRegistry(registry_file)

    assert len(registry.submissions) == 0

    zip_a = tmp_path / "submission_a.zip"
    pack_submission(dummy_condition_dir, zip_a)

    rec1 = registry.register(
        zip_path=zip_a,
        condition="A",
        notes="Línea base A oficial",
        is_exploratory=False,
    )

    assert rec1.submission_id == "sub-001"
    assert rec1.condition == "A"
    assert rec1.sha256 == compute_file_sha256(zip_a)
    assert rec1.size_bytes == zip_a.stat().st_size
    assert rec1.is_exploratory is False
    assert len(registry.submissions) == 1

    # Idempotencia: volver a registrar el mismo zip no duplica
    rec1_again = registry.register(
        zip_path=zip_a,
        condition="A",
        notes="Intento duplicado",
    )
    assert rec1_again.submission_id == "sub-001"
    assert len(registry.submissions) == 1

    # Registrar una segunda condición distinta
    cond_b_dir = tmp_path / "cond_b"
    cond_b_dir.mkdir()
    (cond_b_dir / "agent.yaml").write_text("model: gemma-4-31b-it\ncondition: B\n", encoding="utf-8")
    (cond_b_dir / "eval_config.yaml").write_text("timeout: 3600\n", encoding="utf-8")

    zip_b = tmp_path / "submission_b.zip"
    pack_submission(cond_b_dir, zip_b)

    rec2 = registry.register(
        zip_path=zip_b,
        condition="B",
        notes="Placebo B",
        is_exploratory=True,
    )
    assert rec2.submission_id == "sub-002"
    assert rec2.condition == "B"
    assert rec2.is_exploratory is True
    assert len(registry.submissions) == 2

    # Verificar persistencia en disco
    assert registry_file.is_file()
    data = json.loads(registry_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert len(data["submissions"]) == 2

    # Recargar en una nueva instancia
    registry_reloaded = SubmissionRegistry(registry_file)
    assert len(registry_reloaded.submissions) == 2
    assert registry_reloaded.submissions[0].submission_id == "sub-001"
    assert registry_reloaded.submissions[1].submission_id == "sub-002"


@pytest.mark.usefixtures("compiler_ok")
def test_cli_pack_verify_register_list(
    dummy_condition_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    zip_path = tmp_path / "cli_submission.zip"
    reg_path = tmp_path / "cli_registry.json"

    # 1. pack
    exit_pack = main(["pack", "--condition-dir", str(dummy_condition_dir), "-o", str(zip_path)])
    assert exit_pack == EXIT_OK
    assert zip_path.is_file()

    # 2. verify
    exit_verify = main(["verify", str(zip_path)])
    assert exit_verify == EXIT_OK
    captured = capsys.readouterr()
    assert "Resultado: VÁLIDO" in captured.out

    # 3. register
    exit_reg = main(
        [
            "register",
            "--zip",
            str(zip_path),
            "--condition",
            "A",
            "--notes",
            "Prueba CLI",
            "--registry",
            str(reg_path),
        ]
    )
    assert exit_reg == EXIT_OK
    captured_reg = capsys.readouterr()
    assert "Envío registrado: sub-001" in captured_reg.out

    # 4. list
    exit_list = main(["list", "--registry", str(reg_path)])
    assert exit_list == EXIT_OK
    captured_list = capsys.readouterr()
    assert "sub-001" in captured_list.out
    assert "A" in captured_list.out
