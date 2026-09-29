"""Issue #42: source/test hashes must not depend on the checkout's end-of-line bytes."""

import json
import shutil

import pytest

from experiments import runner
from experiments.evaluate import compare, evaluate, semantic
from experiments.evidence import (
    LEGACY_SOURCE_HASH_NORMALIZATION,
    RECEIPT_SCHEMA,
    SOURCE_HASH_NORMALIZATION,
    hash_normalization,
    normalize_source,
    publish,
    read_receipt,
    source_sha256,
    sources_digest,
)
from experiments.memory import EvidenceMemory
from experiments.runner import ROOT, run_experiment, source_manifest, update_memory

PUBLISHED = ROOT / "evidence/runs"
# Minimal tree a run reads: benchmark inputs, the project under repair and one src file.
TREE = (
    "benchmark/issues.json",
    "benchmark/private/tasks.json",
    "benchmark/public",
    "experiments/software_project",
    "src/experiments/agent.py",
)


def lf(data, suffix):
    return data


def crlf(data, suffix):
    return data.replace(b"\n", b"\r\n")


def crlf_bom(data, suffix):
    # JSON readers reject a BOM; Python sources and tests accept it.
    return (b"\xef\xbb\xbf" if suffix == ".py" else b"") + crlf(data, suffix)


def write_tree(target, transform, alter=None):
    """Copy the git-tracked inputs into ``target`` rewriting every file's bytes."""
    for entry in TREE:
        source = ROOT / entry
        files = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file())
        for path in files:
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(ROOT).as_posix()
            data = normalize_source(path.read_bytes()).encode("utf-8")  # LF baseline
            if alter and relative == alter:
                data += b"# a real, behaviour-neutral content change\n"
            data = transform(data, path.suffix)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    return target


@pytest.fixture
def trees(tmp_path, monkeypatch):
    # The copies are not git checkouts; provenance commit is irrelevant to hashing.
    monkeypatch.setattr(runner, "git_commit", lambda root: "portability-test")
    return {
        "lf": write_tree(tmp_path / "lf", lf),
        "crlf": write_tree(tmp_path / "crlf", crlf),
        "crlf_bom": write_tree(tmp_path / "crlf_bom", crlf_bom),
    }


def run_all(root, evidence):
    """NO_MEMORY on every task plus a trained associative transfer run."""
    receipts = [
        read_receipt(run_experiment(f"EXP-0{i}", evidence_dir=evidence, root=root, batch_id="b"))
        for i in range(1, 7)
    ]
    memory = EvidenceMemory()
    training = run_experiment(
        "EXP-01", memory_mode="ASSOCIATIVE_MEMORY", memory=memory, evidence_dir=evidence, root=root
    )
    update = read_receipt(update_memory(memory, training, evidence))
    transfer = read_receipt(
        run_experiment(
            "EXP-04", memory_mode="ASSOCIATIVE_MEMORY", memory=memory, evidence_dir=evidence, root=root
        )
    )
    return receipts, read_receipt(training), update, transfer


def test_normalization_function():
    assert normalize_source(b"\xef\xbb\xbfa\r\nb\rc\n") == "a\nb\nc\n"
    assert normalize_source("a\r\nb") == "a\nb"
    assert normalize_source("﻿﻿x") == "﻿x"  # only one leading BOM is a BOM
    assert source_sha256(b"x\r\ny\n") == source_sha256("x\ny\n")
    assert sources_digest({"a": b"1\r\n"}) == sources_digest({"a": "1\n"})
    assert source_sha256("x\ny\n") != source_sha256("x\ny \n")  # control


def test_lf_and_crlf_trees_hash_identically(trees, tmp_path):
    assert (trees["lf"] / "benchmark/public/EXP-05_test.py").read_bytes() != (
        trees["crlf"] / "benchmark/public/EXP-05_test.py"
    ).read_bytes()
    manifests = {name: source_manifest(root) for name, root in trees.items()}
    assert manifests["lf"] == manifests["crlf"] == manifests["crlf_bom"]
    results = {name: run_all(root, tmp_path / ("ev-" + name)) for name, root in trees.items()}
    reference = results["lf"]
    for name in ("crlf", "crlf_bom"):
        runs, training, update, transfer = results[name]
        for a, b in zip(
            [*reference[0], reference[1], reference[3]], [*runs, training, transfer], strict=True
        ):
            assert a["schema_id"] == b["schema_id"] == RECEIPT_SCHEMA
            assert a["source_hash_normalization"] == b["source_hash_normalization"] == "lf/v1"
            for key in ("initial_source", "initial_source_sha256", "acceptance_sha256"):
                assert a[key] == b[key], (name, a["task"]["id"], key)
            assert a["provenance"]["source_manifest"] == b["provenance"]["source_manifest"]
            assert [x["inspection_sha256"] for x in a["actions"]] == [
                x["inspection_sha256"] for x in b["actions"]
            ]
            assert semantic(a) == semantic(b)
        # Without run-specific lessons (their ids are UUIDs) context and memory
        # fingerprints must also match exactly.
        for a, b in zip([*reference[0], reference[1]], [*runs, training], strict=True):
            for key in ("agent_context_sha256", "memory_before_sha256", "memory_after_sha256"):
                assert a[key] == b[key], (name, a["task"]["id"], key)
        assert update["source_hash_normalization"] == SOURCE_HASH_NORMALIZATION
        report = compare(tmp_path / "ev-lf", tmp_path / ("ev-" + name))
        assert report["identical"], report


def test_real_content_change_changes_hashes(trees, tmp_path):
    altered = write_tree(tmp_path / "altered", crlf, alter="benchmark/public/EXP-05_test.py")
    changed_app = write_tree(tmp_path / "app", lf, alter="experiments/software_project/app/config.py")
    assert source_manifest(altered) != source_manifest(trees["crlf"])
    base = read_receipt(run_experiment("EXP-05", evidence_dir=tmp_path / "ev-base", root=trees["lf"]))
    test_change = read_receipt(run_experiment("EXP-05", evidence_dir=tmp_path / "ev-alt", root=altered))
    assert test_change["acceptance_sha256"] != base["acceptance_sha256"]
    assert test_change["initial_source_sha256"] == base["initial_source_sha256"]
    app_change = read_receipt(run_experiment("EXP-05", evidence_dir=tmp_path / "ev-app", root=changed_app))
    assert app_change["initial_source_sha256"] != base["initial_source_sha256"]
    report = compare(tmp_path / "ev-base", tmp_path / "ev-alt")
    assert not report["identical"]
    assert report["differences"] == [{"seed": 7, "task": "EXP-05", "mode": "NO_MEMORY", "fields": ["tests"]}]


def test_published_v1_receipts_still_verify_and_reproduce_results(tmp_path):
    paths = sorted(PUBLISHED.glob("RUN-*.json"))
    assert len(paths) == 144
    receipts = [read_receipt(p) for p in paths]
    assert {r["schema_id"] for r in receipts} == {"software-learning-receipt/v1"}
    assert {hash_normalization(r) for r in receipts} == {LEGACY_SOURCE_HASH_NORMALIZATION}
    report = evaluate(PUBLISHED, output=tmp_path)
    published = (ROOT / "results/experiment1.json").read_bytes()
    assert report == json.loads(published)
    assert (tmp_path / "experiment1.json").read_bytes() == published


def test_mixing_normalization_schemes_is_rejected(tmp_path):
    v1 = tmp_path / "v1"
    v1.mkdir()
    task_runs = [p for p in sorted(PUBLISHED.glob("RUN-*.json")) if read_receipt(p)["kind"] == "task_run"]
    legacy = next(p for p in task_runs if read_receipt(p)["task"]["id"] == "EXP-06")
    shutil.copyfile(legacy, v1 / legacy.name)
    v2 = tmp_path / "v2"
    run_experiment("EXP-06", evidence_dir=v2, seed=read_receipt(legacy)["seed"])
    with pytest.raises(ValueError, match="normalization schemes"):
        compare(v1, v2)
    mixed = tmp_path / "mixed"
    shutil.copytree(v2, mixed)
    shutil.copyfile(legacy, mixed / legacy.name)
    with pytest.raises(ValueError, match="normalization schemes"):
        evaluate(mixed)


def test_reader_rejects_undeclared_or_unknown_schemes(tmp_path):
    base = {"run_id": "RUN-a", "kind": "memory_update", "schema_id": RECEIPT_SCHEMA}
    with pytest.raises(ValueError, match="source_hash_normalization"):
        read_receipt(publish(tmp_path, base))
    with pytest.raises(ValueError, match="source_hash_normalization"):
        read_receipt(publish(tmp_path, {**base, "run_id": "RUN-b", "source_hash_normalization": "raw"}))
    legacy = {**base, "run_id": "RUN-c", "schema_id": "software-learning-receipt/v1"}
    with pytest.raises(ValueError, match="v1 receipts"):
        read_receipt(publish(tmp_path, {**legacy, "source_hash_normalization": "lf/v1"}))
    with pytest.raises(ValueError, match="unsupported receipt schema"):
        read_receipt(publish(tmp_path, {**base, "run_id": "RUN-d", "schema_id": "x/v9"}))
