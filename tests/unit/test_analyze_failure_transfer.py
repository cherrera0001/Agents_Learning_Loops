"""Análisis pre-registrado de H7 (#65): validación cerrada de la campaña, métricas y cada lectura.

``analyze`` solo se ejercita sobre campañas sintéticas **completas** con la forma declarada (2 réplicas
× 6 semillas × 18 condiciones × 9 ejecuciones = 1944 ``task_run``, un ``memory_update`` de lecciones por
entrenamiento de las bases C y uno de fallos por ejecución de una variante con intentos fallidos). Un
simulador determinista genera los recibos: cada tarea tiene un operador correcto, cada semilla una
permutación del prior, y un registro aplica si su tarea de origen comparte grupo de firma con la actual y la
similitud declarada alcanza τ. Las lecturas se alcanzan eligiendo grupos o planes; ningún test exige que la
memoria de fallos gane.
"""

import ast
import copy
import inspect
import itertools
import json

import pytest

from experiments.evidence import RECEIPT_SCHEMA, SOURCE_HASH_NORMALIZATION, digest
from scripts import analyze_failure_transfer as analysis
from scripts.analyze_failure_transfer import AGENT, POLICY, STORE, analyze, h7a, h7b, h7c, load

TASKS = [f"EXP-{i:02d}" for i in range(1, 10)]
TRAIN, ORIGINAL, MISLEADING = TASKS[:3], TASKS[3:6], TASKS[6:]
SEEDS = (1, 4, 5, 6, 7, 9)
BATCHES = ("BATCH-a", "BATCH-b")
CONDITIONS = analysis.CONDITIONS
ID, ENV, STO = "validate_optional_identity", "normalize_environment", "initialize_storage"
ROTATE = {ID: ENV, ENV: STO, STO: ID}
PRIORS = dict(zip(SEEDS, itertools.permutations((ID, ENV, STO)), strict=True))
CORRECT = dict(zip(TASKS, [ID, ENV, STO] * 3, strict=True))
DECOY = dict(zip(MISLEADING, [STO, ID, ENV], strict=True))
PRIVATE = {t: {"family": f} for t, f in zip(TASKS, ["auth", "config", "ready"] * 3, strict=True)}
for _task, _decoy in zip(MISLEADING, ["ready", "auth", "config"], strict=True):
    PRIVATE[_task]["decoy_family"] = _decoy
TAUS = ("0.5", "0.25", "0.1", "0.0")


def ordered(strategies):
    return [s for s in (ID, ENV, STO) if s in strategies]


def seal(record):
    return {**record, "receipt_sha256": digest(record)}


def simulate(group=None, similarity=0.2, proposal=None, override=None):
    """Campaña sintética con la forma de ``run --campaign failure-transfer-v1``.

    ``group``: tarea → grupo de firma (por defecto, cada tarea el suyo: ningún registro de otra tarea tiene
    la misma firma). ``similarity``: similitud declarada entre dos tareas distintas (0.2: aplica con τ = 0.1
    y τ = 0). ``proposal``: tarea de transferencia → estrategia que propone la lección en las bases C (por
    defecto la correcta en las originales y el señuelo en las engañosas). ``override(cond, task, seed,
    plan)`` puede sustituir el plan de una ejecución (``None`` = sin cambio).
    """
    group = {t: t for t in TASKS} | (group or {})
    proposal = {**{t: CORRECT[t] for t in ORIGINAL}, **DECOY} | (proposal or {})
    header = {"schema_id": RECEIPT_SCHEMA, "source_hash_normalization": SOURCE_HASH_NORMALIZATION}
    receipts = []
    for batch, seed, cond in itertools.product(BATCHES, SEEDS, CONDITIONS):
        mode, enabled, tau, placebo = CONDITIONS[cond]
        records, lessons, origin = [], [], {}
        for task in TASKS:
            run_id = f"RUN-{batch}-{seed}-{cond}-{task}"
            prior = list(PRIORS[seed])
            wants = proposal.get(task) if mode != "NO_MEMORY" and task not in TRAIN else None
            signature = [{"outcome": "ERROR", "exception": group[task], "none_marker": False}]
            scope, applied, demoted, recorded = [], [], set(), set()
            for x in records:
                match = x["signature"] == signature
                value = similarity(task, origin[x["id"]]) if callable(similarity) else similarity
                demotes = ROTATE[x["strategy"]] if placebo else x["strategy"]
                applies = match and value >= tau
                scope.append(
                    {
                        "strategy": x["strategy"],
                        "signature_match": match,
                        "similarity": value,
                        "applies": applies,
                        "demotes": demotes,
                    }
                )
                if applies:
                    applied.append(x["id"])
                    demoted.add(demotes)
                    recorded.add(x["strategy"])
            base = sorted(prior, key=lambda op, p=wants: (op != p, prior.index(op)))
            plan = sorted(prior, key=lambda op, p=wants, f=demoted: (op in f, op != p, prior.index(op)))
            plan = (override and override(cond, task, seed, plan)) or plan
            if not enabled:
                base = plan
            effect = "none" if not applied else "no_change" if plan[0] == base[0] else "changed_first"
            attempts = plan[: plan.index(CORRECT[task]) + 1]
            exposed = [{"id": lessons[0]["id"], "task": lessons[0]["task"]}] if wants and lessons else []
            record = {
                **header,
                "kind": "task_run",
                "run_id": run_id,
                "agent": AGENT,
                "batch_id": batch,
                "seed": seed,
                "task": {"id": task, "title": "title " + task, "context": "context"},
                "memory_mode": mode,
                "condition": cond,
                "failure_scope_tau": tau,
                "placebo": placebo,
                "split": "train" if task in TRAIN else "transfer",
                "result": "PASS",
                "memory_input": None if mode == "NO_MEMORY" else {"lessons": copy.deepcopy(lessons)},
                "retrieval": {"memories": exposed},
                "decision": {
                    "policy": POLICY,
                    "plan": plan,
                    "memory_ids": [m["id"] for m in exposed],
                    "diagnostic": {"status": "partial", "features": signature},
                    "plan_without_failures": base,
                    "failure_scope": scope,
                    "failure_ids": applied,
                    "failure_strategies": ordered(demoted),
                    "failure_effect": effect,
                    "failure_scope_tau": tau,
                    "failure_placebo": placebo,
                    "failure_recorded_strategies": ordered(recorded),
                },
                "failure_memory_input": copy.deepcopy(records),
                "failure_origins": [{"id": i, "origin": "other_task"} for i in applied],
                "iterations": len(attempts),
                "duration_ms": 1.0,
                "tests": [{"id": "test-0", "returncode": 1}]
                + [
                    {"id": f"test-{i}", "returncode": 0 if s == CORRECT[task] else 1}
                    for i, s in enumerate(attempts, 1)
                ],
                "actions": [{"iteration": i, "strategy": s} for i, s in enumerate(attempts, 1)],
                "outcome": {
                    "success": True,
                    "first_attempt_success": len(attempts) == 1,
                    "iterations": len(attempts),
                },
            }
            record["receipt_sha256"] = digest(record)
            receipts.append(record)
            if task in TRAIN and mode != "NO_MEMORY":
                update = {**header, "kind": "memory_update", "run_id": "RUN-mu" + run_id[3:]}
                receipts.append(seal({**update, "source_receipt": run_id + ".json"}))
                lessons.append(
                    {
                        "id": "lesson:" + run_id,
                        "run_id": run_id,
                        "task": task,
                        "receipt_sha256": record["receipt_sha256"],
                    }
                )
            if enabled:
                new = [
                    {
                        "id": f"failure:{run_id}#test-{i}",
                        "strategy": s,
                        "query": "title " + task + " context",
                        "signature": signature,
                        "evidence": f"{run_id}#test-{i}",
                        "receipt_sha256": record["receipt_sha256"],
                    }
                    for i, s in enumerate(attempts, 1)
                    if s != CORRECT[task]
                ]
                if new:
                    changes = [{"action": "ADD", "memory": x["id"], "evidence": x["evidence"]} for x in new]
                    update = {
                        **header,
                        "kind": "memory_update",
                        "memory_store": STORE,
                        "run_id": "RUN-fm" + run_id[3:],
                    }
                    receipts.append(
                        seal({**update, "source_receipt": run_id + ".json", "memory_changes": changes})
                    )
                records = records + new
                origin.update({x["id"]: task for x in new})
    return receipts


def runs_of(receipts):
    return [r for r in receipts if r["kind"] == "task_run"]


def find(receipts, batch, seed, cond, task):
    key = (batch, seed, cond, task)
    return next(
        r for r in runs_of(receipts) if (r["batch_id"], r["seed"], r["condition"], r["task"]["id"]) == key
    )


# Escenarios. Con el prior de cada semilla (PRIORS) y el operador correcto de cada tarea (CORRECT):
# - TRANSFER: EXP-07 (correcta: identidad; la lección de C propone el señuelo, almacenamiento) comparte firma
#   con EXP-01 (correcta: identidad). En C, los fallos de EXP-01 bajan el señuelo en 3 semillas (6, 7, 9) y
#   el primer intento acierta: helped = 3. El placebo baja otra estrategia y no acierta nunca antes.
# - CONTAMINATION: EXP-04 comparte firma con EXP-02 y EXP-05 con EXP-01. En C, los fallos de la otra tarea
#   bajan justo la estrategia correcta que proponía la lección: hurt = 3 + 3 en las originales.
TRANSFER = {"EXP-07": "EXP-01"}
CONTAMINATION = {"EXP-04": "EXP-02", "EXP-05": "EXP-01"}


def rules(report, rule, base="C", tau="0.0", variant="real"):
    return report["rules"][rule][base][tau][variant]


# --- lecturas pre-registradas -------------------------------------------------------------------


def test_the_default_simulation_is_accepted_with_exact_counts_and_no_exposure():
    receipts = simulate()
    report = analyze(receipts, PRIVATE)
    campaign = report["campaign"]
    assert (campaign["task_runs"], campaign["lesson_memory_updates"]) == (1944, 2 * 6 * 9 * 3)
    assert campaign["failure_memory_updates"] == sum(r.get("memory_store") == STORE for r in receipts) > 0
    assert campaign["batches"] == list(BATCHES) and campaign["primary_batch"] == "BATCH-a"
    assert report["replicates_consistent"] and (report["margin_pairs"], report["pairs_per_cell"]) == (3, 18)
    for base, tau, variant, kind in itertools.product(
        "AC", TAUS, ("real", "placebo"), ("original", "misleading")
    ):
        cell = report["cells"][base][tau][variant][kind]
        assert cell["pairs"] == 18 and cell["exposure"] == "sin exposición"
        assert cell["Exposure"]["numerator"] == cell["Changed"]["numerator"] == 0
        assert (cell["helped"]["numerator"], cell["hurt"]["numerator"], cell["NetTransfer"]) == (0, 0, 0)
        assert cell["base_plan_equal"] == 18 and cell["helped_or_hurt_without_changed"] == 0
    for base, tau in itertools.product("AC", TAUS):
        for variant in ("real", "placebo"):
            assert rules(report, "H7a", base, tau, variant)["verdict"] == "sin exposición"
            h7b_ = rules(report, "H7b", base, tau, variant)
            assert h7b_["verdict"] == "sin exposición"
            assert all(k["hurt_zero_by_construction"] for k in h7b_["kinds"].values())
        assert {c["verdict"] for c in report["rules"]["H7c"][base][tau].values()} == {"sin exposición"}
    assert report["conclusion"] == {
        "verdict": "sin evidencia de transferencia",
        "transfers_at_tau": [],
        "contaminates_at_tau": [],
    }
    assert report["descriptive"]["applied_record_sources"]["C_R00"] == {}
    fa = report["cells"]["C"]["0.0"]["real"]
    assert fa["original"]["FA_base"]["numerator"] == 18 and fa["misleading"]["FA_base"]["numerator"] == 0


def test_a_transfer_that_the_placebo_does_not_reproduce_concludes_transfer_without_contamination():
    report = analyze(simulate(group=TRANSFER), PRIVATE)
    real, placebo = (report["cells"]["C"]["0.0"][v]["misleading"] for v in ("real", "placebo"))
    assert (real["Changed"]["numerator"], real["helped"]["numerator"], real["hurt"]["numerator"]) == (3, 3, 0)
    assert real["exposure"] == "con exposición" and real["NetTransfer"] == 3
    assert (placebo["Changed"]["numerator"], placebo["NetTransfer"]) == (3, 0)
    assert real["Exposure"]["numerator"] == 4  # un registro aplica sin cambiar el primer intento (semilla 5)
    for tau in ("0.1", "0.0"):
        h7b_ = rules(report, "H7b", tau=tau)
        assert h7b_["verdict"] == "transfiere sin contaminar"
        assert h7b_["kinds"]["original"]["hurt_zero_by_construction"]  # marcado, no es evidencia
        assert h7b_["kinds"]["misleading"] == {
            "with_exposure": True,
            "helped_at_least_margin": True,
            "hurt_at_least_margin": False,
            "hurt_zero": True,
            "hurt_zero_by_construction": False,
        }
        assert report["rules"]["H7c"]["C"][tau]["misleading"] == {
            "NetTransfer_real": 3,
            "NetTransfer_placebo": 0,
            "difference": 3,
            "verdict": "el contenido importa",
        }
        assert rules(report, "H7b", tau=tau, variant="placebo")["verdict"] == "neutral"
        assert rules(report, "H7a", tau=tau)["verdict"] == "no contamina"
    for tau in ("0.5", "0.25"):  # similitud 0.2: el alcance no llega
        assert rules(report, "H7b", tau=tau)["verdict"] == "sin exposición"
    assert report["conclusion"] == {
        "verdict": "la memoria de fallos transfiere sin contaminar",
        "transfers_at_tau": ["0.1", "0.0"],
        "contaminates_at_tau": [],
    }
    sources = report["descriptive"]["applied_record_sources"]["C_R00"]
    assert set(sources) == {"EXP-01 -> EXP-07"}
    assert report["descriptive"]["by_task"]["C_R00"]["EXP-07"] == {"Exposure": 4, "Changed": 3}


def test_a_transfer_that_the_placebo_reproduces_is_not_a_transfer_of_content():
    def placebo_too(cond, task, seed, plan):  # el placebo acierta igual que la real en las semillas 6, 7, 9
        if cond in ("C_P10", "C_P00") and task == "EXP-07" and seed in (6, 7, 9):
            return [CORRECT[task]] + [s for s in PRIORS[seed] if s != CORRECT[task]]
        return None

    report = analyze(simulate(group=TRANSFER, override=placebo_too), PRIVATE)
    for tau in ("0.1", "0.0"):
        assert rules(report, "H7b", tau=tau)["verdict"] == "transfiere sin contaminar"
        assert rules(report, "H7b", tau=tau, variant="placebo")["verdict"] == "transfiere sin contaminar"
        c = report["rules"]["H7c"]["C"][tau]["misleading"]
        assert (c["difference"], c["verdict"]) == (0, "indistinguible del placebo")
    assert report["conclusion"] == {
        "verdict": "sin evidencia de transferencia",
        "transfers_at_tau": [],
        "contaminates_at_tau": [],
    }


def test_changed_below_the_margin_leaves_the_cell_without_exposure():
    def undo(cond, task, seed, plan):  # C_R00 vuelve al señuelo en una de las tres semillas cambiadas
        if (cond, task, seed) == ("C_R00", "EXP-07", 7):
            return [DECOY["EXP-07"]] + [s for s in PRIORS[seed] if s != DECOY["EXP-07"]]
        return None

    report = analyze(simulate(group=TRANSFER, override=undo), PRIVATE)
    cell = report["cells"]["C"]["0.0"]["real"]["misleading"]
    assert (cell["Changed"]["numerator"], cell["helped"]["numerator"], cell["exposure"]) == (
        2,
        2,
        "sin exposición",
    )
    assert rules(report, "H7b", tau="0.0")["verdict"] == "sin exposición"
    assert report["rules"]["H7c"]["C"]["0.0"]["misleading"]["verdict"] == "indistinguible del placebo"
    assert report["conclusion"]["transfers_at_tau"] == ["0.1"]


def test_a_contaminating_scope_concludes_contamination_and_is_worse_than_placebo():
    report = analyze(simulate(group=CONTAMINATION), PRIVATE)
    real = report["cells"]["C"]["0.0"]["real"]["original"]
    assert (real["Changed"]["numerator"], real["hurt"]["numerator"], real["helped"]["numerator"]) == (6, 6, 0)
    assert real["FA_variant"]["numerator"] == 12 and real["FA_base"]["numerator"] == 18
    for tau in ("0.1", "0.0"):
        assert rules(report, "H7a", tau=tau)["verdict"] == "contamina"
        assert rules(report, "H7b", tau=tau)["verdict"] == "contamina"
        c = report["rules"]["H7c"]["C"][tau]["original"]
        assert (c["NetTransfer_real"], c["NetTransfer_placebo"], c["verdict"]) == (-6, -3, "peor que placebo")
    assert report["conclusion"] == {
        "verdict": "contamina",
        "transfers_at_tau": [],
        "contaminates_at_tau": ["0.1", "0.0"],
    }


def test_the_threshold_decides_which_tau_is_exposed():
    def sim(target, source):  # EXP-01 → EXP-07 con similitud 0.25 exacta; el resto, nada
        return 0.25 if (source, target) == ("EXP-01", "EXP-07") else 0.0

    report = analyze(simulate(group=TRANSFER, similarity=sim), PRIVATE)
    exposure = {tau: report["cells"]["C"][tau]["real"]["misleading"]["exposure"] for tau in TAUS}
    assert exposure == {
        "0.5": "sin exposición",
        "0.25": "con exposición",
        "0.1": "con exposición",
        "0.0": "con exposición",
    }
    assert report["conclusion"]["transfers_at_tau"] == ["0.25", "0.1", "0.0"]


def test_base_a_is_reported_with_the_same_rules_but_never_enters_the_conclusion():
    def only_a(cond, task, seed, plan):  # C_R/C_P vuelven al plan sin memoria de fallos: C no cambia
        if cond.startswith("C_"):
            wants = DECOY.get(task) if task in MISLEADING else CORRECT.get(task)
            prior = list(PRIORS[seed])
            return sorted(prior, key=lambda op: (op != wants, prior.index(op))) if task not in TRAIN else None
        return None

    report = analyze(simulate(group=TRANSFER, override=only_a), PRIVATE)
    assert rules(report, "H7b", base="A")["verdict"] == "transfiere sin contaminar"
    c = report["cells"]["C"]["0.0"]["real"]["misleading"]
    assert c["Exposure"]["numerator"] > 0 and c["Changed"]["numerator"] == 0  # aplica, pero no cambia nada
    assert rules(report, "H7b", base="C")["verdict"] == "sin exposición"
    assert report["conclusion"]["verdict"] == "sin evidencia de transferencia"


# --- reglas sobre celdas sintéticas -------------------------------------------------------------


def cell(changed=0, helped=0, hurt=0):
    num = lambda n: {"numerator": n, "denominator": 18}  # noqa: E731
    return {
        "Changed": num(changed),
        "helped": num(helped),
        "hurt": num(hurt),
        "NetTransfer": helped - hurt,
        "exposure": "con exposición" if changed >= 3 else "sin exposición",
    }


@pytest.mark.parametrize(
    ("original", "misleading", "a", "b"),
    [
        (cell(), cell(), "sin exposición", "sin exposición"),
        (cell(3, 3), cell(), "no contamina", "transfiere sin contaminar"),
        (cell(3, 2), cell(), "no contamina", "neutral"),
        (cell(3, 3, 0), cell(3, 0, 1), "no contamina", "neutral"),  # hurt = 1 en el otro tipo
        (cell(6, 3, 3), cell(), "contamina", "contamina"),
        (cell(3, 0, 2), cell(9, 9, 0), "no contamina", "neutral"),
        (
            cell(2, 0, 2),
            cell(9, 9, 0),
            "no contamina",
            "transfiere sin contaminar",
        ),  # sin exposición: no se lee
        (cell(2, 2, 0), cell(), "sin exposición", "sin exposición"),
    ],
)
def test_h7a_and_h7b_follow_the_preregistered_rules(original, misleading, a, b):
    cells = {"original": original, "misleading": misleading}
    assert h7a(cells)["verdict"] == a
    assert h7b(cells)["verdict"] == b


@pytest.mark.parametrize(
    ("real", "placebo", "verdict"),
    [
        (cell(3, 3), cell(3), "el contenido importa"),
        (cell(3, 2), cell(3), "indistinguible del placebo"),
        (cell(3, 0, 2), cell(3), "indistinguible del placebo"),
        (cell(3, 0, 3), cell(3), "peor que placebo"),
        (cell(0), cell(3, 0, 3), "el contenido importa"),  # exposición solo en el placebo
        (cell(2, 2), cell(1), "sin exposición"),
    ],
)
def test_h7c_compares_net_transfer_with_the_placebo(real, placebo, verdict):
    assert h7c(real, placebo)["verdict"] == verdict
    assert h7c(real, placebo)["difference"] == real["NetTransfer"] - placebo["NetTransfer"]


# --- validación cerrada de la campaña -----------------------------------------------------------


DECLARED = "no es la campaña declarada"


def _without(predicate):
    return [r for r in simulate() if not predicate(r)]


@pytest.mark.parametrize(
    ("receipts", "message"),
    [
        (_without(lambda r: "BATCH-b" in r["run_id"]), "réplicas"),
        (_without(lambda r: r["run_id"] == "RUN-BATCH-a-5-C_P25-EXP-09"), DECLARED),
        (_without(lambda r: r["kind"] == "task_run" and r["condition"] == "A_R10"), DECLARED),
        (_without(lambda r: r["run_id"] == "RUN-mu-BATCH-a-4-C_R50-EXP-02"), "memory_update de lecciones"),
        (_without(lambda r: r["run_id"].startswith("RUN-fm-BATCH-b-7-A_P00")), "memory_update de fallos"),
    ],
    ids=["replicate", "one-run", "one-condition", "lesson-update", "failure-update"],
)
def test_incomplete_campaigns_are_rejected(receipts, message):
    with pytest.raises(ValueError, match=message):
        analyze(receipts, PRIVATE)


def renamed(r, **changes):
    r = copy.deepcopy(r)
    r.update(changes)
    r["run_id"] = f"RUN-{r['batch_id']}-{r['seed']}-{r['condition']}-{r['task']['id']}-copy"
    return r


def test_duplicates_unexpected_seeds_and_batches_are_rejected():
    base = simulate()
    run = find(base, "BATCH-a", 5, "A", "EXP-04")
    for receipts, message in (
        ([*base, renamed(run)], "celda duplicada"),
        ([*base, renamed(run, seed=2)], DECLARED),
        (
            [*base, *(renamed(r, batch_id="BATCH-c") for r in runs_of(base) if r["batch_id"] == "BATCH-a")],
            "réplicas",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            analyze(receipts, PRIVATE)


def test_replicates_that_differ_in_behaviour_are_rejected():
    receipts = simulate()
    replica = find(receipts, "BATCH-b", 4, "C_R25", "EXP-05")
    replica["outcome"] = {**replica["outcome"], "iterations": 9}
    with pytest.raises(ValueError, match="réplicas difieren"):
        analyze(receipts, PRIVATE)
    receipts = simulate(group=TRANSFER)
    replica = find(receipts, "BATCH-b", 6, "C_R00", "EXP-07")
    replica["failure_origins"] = [{**o, "origin": "same_task"} for o in replica["failure_origins"]]
    with pytest.raises(ValueError, match="misma tarea"):
        analyze(receipts, PRIVATE)


def _mutated(change, batch="BATCH-a", seed=6, cond="C_R00", task="EXP-07", group=TRANSFER):
    receipts = simulate(group=group)
    change(find(receipts, batch, seed, cond, task), receipts)
    return receipts


def _self_record(r, rs):
    """Un registro del propio intento fallido de la ejecución, aplicado: su origen es la misma tarea."""
    evidence = r["run_id"] + "#test-1"
    record = {**r["failure_memory_input"][0], "id": "failure:" + evidence, "evidence": evidence}
    r["failure_memory_input"].append(record)
    r["decision"]["failure_ids"].append(record["id"])
    r["failure_origins"].append({"id": record["id"], "origin": "other_task"})


def _other_condition_record(r, rs):
    """Un registro del mismo EXP-07 en otra condición, aplicado y declarado como de otra tarea."""
    donor = find(rs, "BATCH-a", 6, "A", "EXP-07")
    evidence = donor["run_id"] + "#test-1"
    record = {**r["failure_memory_input"][0], "id": "failure:" + evidence, "evidence": evidence}
    r["failure_memory_input"].append(record)
    r["decision"]["failure_ids"].append(record["id"])
    r["failure_origins"].append({"id": record["id"], "origin": "other_task"})


def _scope(field, value):
    def change(r, rs):
        r["decision"]["failure_scope"][0][field] = value

    return change


@pytest.mark.parametrize(
    ("change", "kwargs", "message"),
    [
        (_self_record, {}, "misma tarea"),
        (_other_condition_record, {}, "misma tarea"),
        (lambda r, rs: r["failure_origins"][0].update(origin="same_task"), {}, "misma tarea"),
        (
            lambda r, rs: r["failure_memory_input"].append(
                copy.deepcopy(find(rs, "BATCH-a", 6, "C_R00", "EXP-07")["failure_memory_input"][0])
            ),
            {"cond": "C"},
            "base C con memoria de fallos",
        ),
        (lambda r, rs: r["decision"]["failure_ids"].append("failure:x"), {"cond": "A"}, "base A"),
        (
            lambda r, rs: r["failure_memory_input"][0].update(
                evidence=find(rs, "BATCH-a", 6, "C_R00", "EXP-09")["run_id"] + "#test-1"
            ),
            {},
            "no anterior",
        ),
        (
            lambda r, rs: r["failure_memory_input"][0].update(
                evidence=r["failure_memory_input"][0]["evidence"].replace("#test-1", "#test-0")
            ),
            {},
            "no cita un intento",
        ),
        (lambda r, rs: r["failure_memory_input"][0].update(strategy=STO), {}, "no coincide con su recibo"),
        (lambda r, rs: r["decision"]["failure_scope"].pop(), {}, "alcance sin un elemento"),
        (lambda r, rs: r["failure_memory_input"].pop(), {}, "no es la de los intentos fallidos"),
        (_scope("applies", False), {}, "alcance o placebo incoherentes"),
        (_scope("similarity", 0.0), {"cond": "C_R10"}, "alcance o placebo incoherentes"),
        (_scope("demotes", ENV), {"cond": "C_P00"}, "alcance o placebo incoherentes"),
        (lambda r, rs: r["decision"].update(failure_strategies=[STO]), {}, "decisión incoherente"),
        (
            lambda r, rs: r["decision"].update(failure_recorded_strategies=[]),
            {},
            "decisión incoherente",
        ),
        (lambda r, rs: r["decision"].update(failure_effect="no_change"), {}, "decisión incoherente"),
        (lambda r, rs: r["failure_origins"].pop(), {}, "orígenes"),
    ],
    ids=[
        "own-run",
        "other-condition",
        "declared-same",
        "records-in-c",
        "applied-in-a",
        "later-run",
        "cites-test-0",
        "strategy",
        "scope-length",
        "incomplete-memory",
        "applies",
        "similarity-below-tau",
        "placebo-demotes",
        "demoted",
        "recorded",
        "effect",
        "origins",
    ],
)
def test_failure_records_and_decisions_must_derive_from_earlier_failed_attempts(change, kwargs, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change, **kwargs), PRIVATE)


def test_failure_updates_must_derive_from_their_run_and_exist_only_for_the_variants():
    receipts = simulate()
    update = next(u for u in receipts if u.get("memory_store") == STORE)
    update["memory_changes"] = [*update["memory_changes"][:-1], {"evidence": "x"}]
    with pytest.raises(ValueError, match="no deriva de su recibo"):
        analyze(receipts, PRIVATE)
    receipts = simulate()
    source = next(r for r in runs_of(receipts) if r["condition"] == "A" and len(r["tests"]) > 2)
    extra = {"kind": "memory_update", "memory_store": STORE, "run_id": "RUN-fm-extra", "memory_changes": []}
    with pytest.raises(ValueError, match="memory_update de fallos"):
        analyze([*receipts, {**extra, "source_receipt": source["run_id"] + ".json"}], PRIVATE)
    with pytest.raises(ValueError, match="memoria no prevista"):
        analyze([*receipts, {**extra, "memory_store": "other"}], PRIVATE)


@pytest.mark.parametrize(
    ("change", "kwargs", "message"),
    [
        (
            lambda r, rs: r["memory_input"]["lessons"].append(
                {"run_id": find(rs, "BATCH-a", 6, "C", "EXP-01")["run_id"], "receipt_sha256": "?"}
            ),
            {},
            "lección fuera de procedencia",
        ),
        (lambda r, rs: r["memory_input"]["lessons"].pop(), {}, "no congelada"),
        (
            lambda r, rs: r["retrieval"]["memories"].append({"id": "m", "task": "EXP-01"}),
            {"cond": "A_R00"},
            "con lecciones",
        ),
        (
            lambda r, rs: r["retrieval"]["memories"].append({"id": "m", "task": "EXP-01"}),
            {"cond": "C"},
            "recuperación fuera",
        ),
    ],
    ids=["lesson-from-c", "not-frozen", "retrieval-in-a", "retrieval-outside"],
)
def test_lessons_follow_their_condition_and_stay_frozen_after_training(change, kwargs, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change, **kwargs), PRIVATE)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda r, rs: r.update(agent="bounded-ast-repair-v1+diagnostic-v1+failure-memory-v1"),
            "solo recibos",
        ),
        (lambda r, rs: r["decision"].update(policy="failure-memory/v1"), "solo recibos"),
        (lambda r, rs: r.update(result="ERROR"), "resultado ERROR"),
        (lambda r, rs: r.pop("placebo"), "sin los campos"),
        (lambda r, rs: r["decision"].pop("failure_recorded_strategies"), "sin los campos"),
        (lambda r, rs: r.update(**{"pass": 1}), "una sola pasada"),
        (lambda r, rs: r.update(memory_mode="NO_MEMORY"), "no concuerda con el modo"),
        (lambda r, rs: r.update(condition="C_R75"), "condición desconocida"),
        (lambda r, rs: r.update(failure_scope_tau=0.5), "alcance τ o placebo"),
        (lambda r, rs: r.update(placebo=True), "alcance τ o placebo"),
        (lambda r, rs: r["decision"].update(failure_scope_tau=0.1), "alcance τ o placebo"),
        (lambda r, rs: r["decision"].update(failure_placebo=True), "alcance τ o placebo"),
        (lambda r, rs: r["decision"].update(failure_effect="maybe"), "efecto"),
        (lambda r, rs: r.update(split="train"), "particiones"),
    ],
    ids=[
        "agent",
        "policy",
        "error",
        "record-field",
        "decision-field",
        "pass",
        "mode",
        "condition",
        "tau",
        "placebo",
        "decision-tau",
        "decision-placebo",
        "effect",
        "split",
    ],
)
def test_other_agents_errors_and_malformed_receipts_are_rejected(change, message):
    with pytest.raises(ValueError, match=message):
        analyze(_mutated(change), PRIVATE)


def test_original_and_misleading_tasks_must_be_the_declared_ones():
    private = {**PRIVATE, "EXP-04": {**PRIVATE["EXP-04"], "decoy_family": "config"}}
    private["EXP-07"] = {k: v for k, v in PRIVATE["EXP-07"].items() if k != "decoy_family"}
    with pytest.raises(ValueError, match="particiones"):
        analyze(simulate(), private)


def test_unknown_receipt_kinds_are_rejected():
    with pytest.raises(ValueError, match="tipo no previsto"):
        analyze([*simulate(), {"kind": "other"}], PRIVATE)


# --- carga sellada, constantes y salida ---------------------------------------------------------


def write(tmp_path, receipts):
    for r in receipts:
        (tmp_path / (r["run_id"] + ".json")).write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")


def test_main_is_deterministic_and_cites_every_sealed_receipt(tmp_path, monkeypatch, capsys):
    receipts = simulate(group=TRANSFER)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    write(evidence, receipts)
    monkeypatch.setattr(analysis, "annotations", lambda root: PRIVATE)
    outputs = []
    for _ in range(2):
        monkeypatch.setattr("sys.argv", ["analyze", "--root", str(tmp_path), "--evidence", "evidence"])
        analysis.main()
        outputs.append(capsys.readouterr().out)
    assert outputs[0] == outputs[1]
    report = json.loads(outputs[0])
    assert report["generated_from"] == {r["run_id"] + ".json": r["receipt_sha256"] for r in receipts}
    assert report["conclusion"]["verdict"] == "la memoria de fallos transfiere sin contaminar"


def test_load_verifies_seals_schemas_and_names(tmp_path):
    record = seal(
        {
            "schema_id": RECEIPT_SCHEMA,
            "source_hash_normalization": SOURCE_HASH_NORMALIZATION,
            "run_id": "RUN-a",
            "kind": "memory_update",
            "note": "ñandú",
        }
    )
    write(tmp_path, [record])
    loaded, generated_from = load(tmp_path)
    assert generated_from == {"RUN-a.json": record["receipt_sha256"]} and loaded == [record]
    (tmp_path / "RUN-a.json").write_text(json.dumps({**record, "note": "otra"}), encoding="utf-8")
    with pytest.raises(ValueError, match="sello"):
        load(tmp_path)
    for change, message in (
        ({"schema_id": "software-learning-receipt/v1"}, "esquema"),
        ({"run_id": "RUN-b"}, "nombre del archivo"),
    ):
        bad = {k: v for k, v in record.items() if k != "receipt_sha256"} | change
        (tmp_path / "RUN-a.json").write_text(json.dumps(seal(bad)), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load(tmp_path)


def test_script_constants_match_the_declared_campaign_and_it_imports_only_stdlib():
    from experiments.agent import STRATEGIES
    from experiments.benchmark import FAILURE_TRANSFER_CAMPAIGN, TASK_SETS
    from experiments.evidence import RECEIPT_SCHEMA as SCHEMA
    from experiments.failure_memory import STORE as FAILURE_STORE
    from experiments.failure_transfer import AGENT_NAME, CONDITIONS, ROTATION, TAUS
    from experiments.failure_transfer import POLICY as TRANSFER_POLICY

    campaign = FAILURE_TRANSFER_CAMPAIGN
    assert (campaign["seeds"], campaign["replicates"]) == (analysis.SEEDS, analysis.REPLICATES)
    assert TASK_SETS[campaign["task_set"]] == analysis.TASKS
    assert (campaign["train"], campaign["transfer"]) == (analysis.TRAIN, analysis.TRANSFER)
    assert campaign["conditions"] == tuple(analysis.CONDITIONS) and campaign["passes"] == 1
    assert analysis.CONDITIONS == CONDITIONS and analysis.TAUS == TAUS
    assert analysis.STRATEGIES == STRATEGIES and analysis.ROTATION == ROTATION
    assert analysis.AGENT == AGENT_NAME == campaign["agent"]
    assert (analysis.POLICY, analysis.STORE) == (TRANSFER_POLICY, FAILURE_STORE)
    assert (analysis.RECEIPT_SCHEMA, analysis.NORMALIZATION) == (SCHEMA, SOURCE_HASH_NORMALIZATION)
    assert analysis.MARGIN == 3 and analysis.PAIRS_PER_CELL == 18
    tree = ast.parse(inspect.getsource(analysis))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= {
        "__future__",
        "argparse",
        "collections",
        "hashlib",
        "itertools",
        "json",
        "pathlib",
        "sys",
        "typing",
    }
