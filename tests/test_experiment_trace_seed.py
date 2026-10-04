"""Siembra con los componentes de la traza (H8, #98): la señal, la siembra y el agente, con trazas sintéticas.

Ningún test ejecuta una tarea real ni dice qué lección recupera una tarea del banco: las trazas, las claves
de archivo y las memorias son sintéticas. Especificación: ``docs/preregistration/h8-nonlexical-seed.md``,
secciones 2 y 8.
"""

import ast
import inspect
import itertools
from pathlib import Path

import pytest

from associative_agent_loop.memory.text import cosine_similarity
from experiments import nonlexical_seed, trace_seed
from experiments.agent import STRATEGIES, AgentView, BoundedRepairAgent
from experiments.benchmark import NONLEXICAL_SEED_CAMPAIGN, REFERENCE_CAMPAIGN, TASK_SETS
from experiments.memory import EvidenceMemory
from experiments.models import MemoryDocument
from experiments.nonlexical_seed import (
    AGENT_NAME,
    CONDITIONS,
    DECISION_INPUTS,
    LEXICAL,
    TRACE,
    TraceSeedRepairAgent,
    condition_of,
    retrieval_inputs,
    retrieve,
)
from experiments.trace_seed import (
    EMPTY,
    POLICY,
    SEEDED,
    TIE,
    component_seeds,
    seeded_retrieval,
    spread,
    trace_components,
    trace_weights,
)

FILES = ("app/api.py", "app/auth.py", "app/config.py", "app/services/reporting.py")
SEPARATOR, DASHES = "=" * 70, "-" * 70
TRACEBACK = "Traceback (most recent call last):"
TEST_FRAME = ("<workspace>/tests/test_contract.py", 12, "test_case", "self.check()")
STDLIB_FRAME = ("/usr/lib/python3.13/unittest/case.py", 58, "testPartExecutor", "yield")


def frame(path, line=1, function="f", code="call()"):
    return f'  File "{path}", line {line}, in {function}\n    {code}'


def app(name, line=1, function="f", code="call()"):
    return ("<workspace>/" + name, line, function, code)


def traceback(frames, exception="ValueError: boom"):
    return "\n".join([TRACEBACK, *(frame(*f) for f in frames), exception])


def block(*tracebacks, outcome="ERROR", test="test_case (tests.test_contract.Case.test_case)"):
    """Un bloque de fallo de ``unittest``; varias trazas = excepciones encadenadas."""
    chained = "\n\nDuring handling of the above exception, another exception occurred:\n\n".join(tracebacks)
    return f"{SEPARATOR}\n{outcome}: {test}\n{DASHES}\n{chained}\n"


def stderr(*blocks, ran=1):
    preface = "test_case (tests.test_contract.Case.test_case) ... ERROR\n\n"
    return preface + "\n".join(blocks) + f"\n{DASHES}\nRan {ran} test in 0.012s\n\nFAILED (errors={ran})\n"


def weights(text, files=FILES):
    return trace_weights(text, files)


def lesson_graph(run, task, strategy, component):
    """El subgrafo que ``EvidenceMemory.consolidate`` escribe para una lección, con sus mismos nodos."""
    key, refs = "lesson:" + run, [run + "#test-1"]
    labels = {
        "Task": "title of " + task,
        "Experience": run,
        "Symptom": "title of " + task + " context of " + task,
        "Cause": "Candidate mechanism supported by repair: " + strategy,
        "Strategy": strategy,
        "Evidence": refs[-1],
        "Lesson": "rule for " + strategy,
        "Component": component,
    }
    ids = {t: key if t == "Lesson" else t.lower() + ":" + run for t in labels}
    nodes = [{"id": ids[t], "type": t, "label": label, "evidence": refs} for t, label in labels.items()]
    edges = [
        {"source": ids[a], "target": ids[b], "relation": relation}
        for a, b, relation in [
            ("Task", "Experience", "related_to"),
            ("Symptom", "Task", "related_to"),
            ("Experience", "Lesson", "related_to"),
            ("Symptom", "Cause", "caused_by"),
            ("Cause", "Strategy", "solved_by"),
            ("Evidence", "Lesson", "evidence_for"),
            ("Lesson", "Strategy", "related_to"),
            ("Lesson", "Component", "applies_to"),
        ]
    ]
    lesson = {
        "id": key,
        "run_id": run,
        "task": task,
        "symptom": labels["Symptom"],
        "strategy": strategy,
        "rule": labels["Lesson"],
        "evidence": refs,
        "receipt_sha256": "0" * 64,
    }
    return nodes, edges, lesson


def document(*lessons):
    """Memoria sintética: una lección por (tarea de origen, componente), validada con el esquema real."""
    nodes, edges, records = [], [], []
    for i, (task, component) in enumerate(lessons):
        n, e, lesson = lesson_graph(f"RUN-{i}", task, STRATEGIES[i % len(STRATEGIES)], component)
        nodes, edges, records = nodes + n, edges + e, [*records, lesson]
    return MemoryDocument.model_validate({"nodes": nodes, "edges": edges, "lessons": records}).model_dump(
        mode="json"
    )


MEMORY = document(("T-auth", "app/auth.py"), ("T-config", "app/config.py"), ("T-api", "app/api.py"))


def exposed(text, memory=MEMORY, files=FILES):
    memories, _, seeding = seeded_retrieval(memory, text, files)
    return [m["task"] for m in memories], seeding["state"]


# --- la señal: componentes de la traza ------------------------------------------------------------


def test_weight_decreases_with_the_distance_to_the_raising_frame():
    text = stderr(block(traceback([TEST_FRAME, app("app/api.py"), app("app/auth.py"), STDLIB_FRAME])))
    assert weights(text) == {"app/api.py": 1 / 2, "app/auth.py": 1.0}
    deep = stderr(block(traceback([app("app/api.py"), app("app/auth.py"), app("app/config.py")])))
    assert weights(deep) == {"app/api.py": 1 / 3, "app/auth.py": 1 / 2, "app/config.py": 1.0}
    assert trace_components(deep, FILES) == [
        {"component": "app/api.py", "weight": 1 / 3},
        {"component": "app/auth.py", "weight": 1 / 2},
        {"component": "app/config.py", "weight": 1.0},
    ]


def test_a_component_counts_by_its_innermost_appearance():
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py"), app("app/api.py")])))
    assert weights(text) == {"app/api.py": 1.0, "app/auth.py": 1 / 2}


def test_a_trace_without_application_frames_gives_no_component():
    assertion = stderr(block(traceback([TEST_FRAME], "AssertionError: 1 != 2"), outcome="FAIL"))
    assert weights(assertion) == {} and trace_components(assertion, FILES) == []
    assert weights(stderr(block(traceback([STDLIB_FRAME])))) == {}
    assert weights("") == {} and weights(None) == {}
    assert exposed(assertion) == ([], EMPTY)


def test_only_the_last_trace_of_a_chained_exception_counts():
    first = traceback([app("app/auth.py")], "KeyError: 'x'")
    last = traceback([app("app/api.py"), app("app/config.py")], "RuntimeError: wrapped")
    assert weights(stderr(block(first, last))) == {"app/api.py": 1 / 2, "app/config.py": 1.0}
    # Si la última traza no pasa por la aplicación, el bloque no aporta nada: no se vuelve a la anterior.
    assert weights(stderr(block(first, traceback([TEST_FRAME])))) == {}


def test_a_block_without_a_traceback_line_gives_nothing():
    lines = f"{SEPARATOR}\nERROR: test_case\n{DASHES}\n{frame('<workspace>/app/auth.py')}\nValueError: x\n"
    assert weights(lines) == {}
    indented = lines.replace(f"{DASHES}\n", f"{DASHES}\n  {TRACEBACK}\n")  # no es la línea exacta
    assert weights(indented) == {}


def test_frames_outside_a_failure_block_are_ignored():
    stray = traceback([app("app/auth.py")]) + "\n"
    assert weights(stray) == {}  # sin cabecera ERROR: / FAIL:
    warning = f"{SEPARATOR}\nWARNING: not a failure\n{DASHES}\n{stray}"
    assert weights(warning) == {}
    assert weights(stray + stderr(block(traceback([app("app/config.py")])))) == {"app/config.py": 1.0}


def test_the_final_summary_is_cut_like_the_diagnosis_does():
    text = stderr(block(traceback([app("app/config.py")])))
    trailer = text + traceback([app("app/auth.py")]) + "\n"  # una traza después de «Ran N tests»
    assert weights(trailer) == weights(text) == {"app/config.py": 1.0}


def test_backslash_and_slash_paths_and_crlf_give_the_same_components():
    text = stderr(block(traceback([app("app/api.py"), app("app/services/reporting.py")])))
    expected = {"app/api.py": 1 / 2, "app/services/reporting.py": 1.0}
    assert weights(text) == expected
    assert weights(text.replace("/", "\\")) == expected
    assert weights(text.replace("\n", "\r\n")) == expected
    assert weights("\ufeff" + text) == expected


def test_two_blocks_take_the_maximum_weight_per_component():
    one = block(traceback([app("app/api.py"), app("app/auth.py")]))
    two = block(traceback([app("app/auth.py"), app("app/api.py"), app("app/config.py")]), outcome="FAIL")
    assert weights(stderr(one, two, ran=2)) == {"app/api.py": 1 / 2, "app/auth.py": 1.0, "app/config.py": 1.0}
    assert weights(stderr(two, one, ran=2)) == weights(stderr(one, two, ran=2))  # sin orden entre bloques


def test_a_frame_belongs_to_a_component_only_after_a_path_separator():
    for path in ("<workspace>/xapp/api.py", "app/api.py", "<workspace>/app/api.pyc", "<workspace>/api.py"):
        assert weights(stderr(block(traceback([(path, 1, "f", "x")])))) == {}, path
    nested = stderr(block(traceback([("C:\\tmp\\aal-task-1\\app\\services\\reporting.py", 3, "f", "x")])))
    assert weights(nested) == {"app/services/reporting.py": 1.0}
    # Si dos claves casan con la misma ruta, gana la más específica.
    files = ("app/api.py", "pkg/app/api.py")
    assert trace_weights(stderr(block(traceback([app("pkg/app/api.py")]))), files) == {"pkg/app/api.py": 1.0}


def test_everything_but_the_path_of_a_frame_is_discarded():
    base = stderr(block(traceback([app("app/api.py"), app("app/auth.py")], "ValueError: boom")))
    variants = [
        stderr(
            block(
                traceback(
                    [
                        app("app/api.py", 99, "authorize", "raise Unauthorized()"),
                        app("app/auth.py", 7, "normalize_environment", "os.getenv('X')"),
                    ],
                    "sqlite3.OperationalError: no such table: NoneType",
                ),
                outcome="FAIL",
                test="test_other (tests.test_business.Other.test_other)",
            )
        ),
        base.replace("test_case", "test_initialize_storage"),
    ]
    for variant in variants:
        assert weights(variant) == weights(base) == {"app/api.py": 1 / 2, "app/auth.py": 1.0}


# --- la siembra y sus estados ---------------------------------------------------------------------


def test_only_component_nodes_with_a_positive_score_are_seeded():
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    seeds = component_seeds(text, FILES, MEMORY["nodes"])
    assert seeds == [{"node": "component:RUN-0", "score": 1.0}, {"node": "component:RUN-2", "score": 1 / 2}]
    # Ningún otro tipo de nodo se siembra, aunque su etiqueta sea la ruta de la traza.
    decoys = [
        {"id": f"{kind.lower()}:x", "type": kind, "label": "app/auth.py"}
        for kind in ("Lesson", "Symptom", "Cause", "Strategy", "Task", "Experience", "Evidence", "Skill")
    ]
    assert component_seeds(text, FILES, decoys) == []
    assert component_seeds(text, FILES, [{"id": "c", "type": "Component", "label": "app/auth.py"}]) == [
        {"node": "c", "score": 1.0}
    ]


def test_a_component_with_several_paths_scores_by_its_best_path():
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    node = {"id": "c", "type": "Component", "label": "app/config.py app/api.py app/auth.py"}
    assert component_seeds(text, FILES, [node]) == [{"node": "c", "score": 1.0}]
    assert component_seeds(text, FILES, [{**node, "label": "app/config.py app/api.py"}]) == [
        {"node": "c", "score": 1 / 2}
    ]
    assert component_seeds(text, FILES, [{**node, "label": ""}]) == []


def test_seeded_exposes_the_lesson_of_the_component_closest_to_the_exception():
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    memories, paths, seeding = seeded_retrieval(MEMORY, text, FILES)
    assert [m["task"] for m in memories] == ["T-auth"]
    assert seeding == {
        "policy": POLICY,
        "components": [
            {"component": "app/api.py", "weight": 1 / 2},
            {"component": "app/auth.py", "weight": 1.0},
        ],
        "seeds": [{"node": "component:RUN-0", "score": 1.0}, {"node": "component:RUN-2", "score": 1 / 2}],
        "state": SEEDED,
        "lesson": "lesson:RUN-0",
    }
    assert [p["memory"] for p in paths] == ["lesson:RUN-0"]
    assert paths[0]["path"] == ["component:RUN-0", "lesson:RUN-0"] and paths[0]["activation"] >= 0.005
    # Al revés, la lección es la otra: decide la traza, no el orden de la memoria ni el de las tareas.
    reverse = stderr(block(traceback([app("app/auth.py"), app("app/api.py")])))
    assert exposed(reverse) == (["T-api"], SEEDED)
    # El punto de entrada gana cuando ningún otro componente con lección aparece en la traza.
    entry = stderr(block(traceback([app("app/api.py"), app("app/services/reporting.py")])))
    assert exposed(entry) == (["T-api"], SEEDED)


def test_a_tie_between_two_component_nodes_exposes_no_lesson():
    twins = document(("T-b", "app/auth.py"), ("T-a", "app/auth.py"), ("T-api", "app/api.py"))
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    memories, paths, seeding = seeded_retrieval(twins, text, FILES)
    assert (memories, paths, seeding["state"], seeding["lesson"]) == ([], [], TIE, None)
    assert [s["score"] for s in seeding["seeds"]] == [1.0, 1.0, 1 / 2]
    # Un empate por debajo del máximo no impide sembrar: el máximo es de un solo nodo.
    below = document(("T-b", "app/api.py"), ("T-a", "app/api.py"), ("T-auth", "app/auth.py"))
    assert exposed(text, below) == (["T-auth"], SEEDED)
    # Dos bloques con el mismo peso para dos componentes: empate entre lecciones distintas.
    two = stderr(block(traceback([app("app/auth.py")])), block(traceback([app("app/config.py")])), ran=2)
    assert exposed(two) == ([], TIE)


def test_empty_when_nothing_is_seeded_or_the_memory_is_empty():
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    assert seeded_retrieval(document(), text, FILES) == (
        [],
        [],
        {
            "policy": POLICY,
            "components": trace_components(text, FILES),
            "seeds": [],
            "state": EMPTY,
            "lesson": None,
        },
    )
    unrelated = stderr(block(traceback([app("app/services/reporting.py")])))
    assert exposed(unrelated) == ([], EMPTY)  # el archivo de la traza no tiene lección


def test_empty_when_the_lesson_does_not_reach_the_activation_cut():
    far = stderr(block(traceback([app("app/auth.py"), *[app("app/api.py")] * 400])))
    memory = document(("T-auth", "app/auth.py"))
    memories, _, seeding = seeded_retrieval(memory, far, FILES)
    assert seeding["seeds"] == [{"node": "component:RUN-0", "score": 1 / 401}]
    assert (memories, seeding["state"], seeding["lesson"]) == ([], EMPTY, None)
    near = stderr(block(traceback([app("app/auth.py"), *[app("app/api.py")] * 3])))
    assert exposed(near, memory) == (["T-auth"], SEEDED)  # control: la misma lección, más cerca


def test_a_lesson_that_does_not_come_from_the_top_component_is_refused():
    crossed = document(("T-auth", "app/auth.py"), ("T-api", "app/api.py"))
    # Fuera del diseño: el componente de mayor puntuación deja de estar unido a su propia lección.
    crossed["edges"] = [e for e in crossed["edges"] if e["target"] != "component:RUN-0"]
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    with pytest.raises(ValueError, match="no procede del componente de mayor puntuación"):
        seeded_retrieval(crossed, text, FILES)


def test_propagation_cut_and_top_one_are_those_of_the_default_retrieval():
    """Con las semillas léxicas de H4, ``spread`` devuelve exactamente lo que ``EvidenceMemory.retrieve``."""
    memory = document(("T-auth", "app/auth.py"), ("T-config", "app/config.py"), ("T-api", "app/api.py"))
    compared = 0
    for query in ("title of T-config context", "rule for " + STRATEGIES[0], "app api py", "nothing shared"):
        seeds = {
            n["id"]: cosine_similarity(query, n["label"])
            for n in memory["nodes"]
            if n["type"] in ("Symptom", "Component", "Lesson")
            and cosine_similarity(query, n["label"]) >= 0.12
        }
        expected = EvidenceMemory(memory).retrieve(query, "ASSOCIATIVE_MEMORY")
        assert spread(memory, seeds) == expected
        compared += bool(expected[0])
    assert compared >= 3  # control: la comparación no es entre dos listas vacías


# --- auditoría del módulo de siembra --------------------------------------------------------------


def imports_of(module):
    tree = ast.parse(Path(module.__file__).read_text("utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    return names


def test_the_seeding_module_sees_only_public_material():
    assert imports_of(trace_seed) == {
        "re",
        "associative_agent_loop.memory.associative",
        "associative_agent_loop.memory.graph",
        ".evidence",
    }
    source = Path(trace_seed.__file__).read_text("utf-8")
    for forbidden in ("EXP-", "benchmark", "private", "open(", "read_text", "Path", "json", *STRATEGIES):
        assert forbidden not in source, forbidden
    for word in ("family", "decoy", "hidden_cause", "mutation", "task_id"):
        assert word not in source, word
    # La función de siembra no recibe la tarea ni su identificador.
    assert list(inspect.signature(component_seeds).parameters) == ["stderr", "files", "nodes"]
    assert list(inspect.signature(seeded_retrieval).parameters) == ["document", "stderr", "files"]
    assert list(inspect.signature(trace_components).parameters) == ["stderr", "files"]


def test_the_opt_in_agent_module_does_not_import_the_controller_or_the_evaluator():
    assert imports_of(nonlexical_seed) == {".agent", ".memory", ".trace_seed"}
    source = Path(nonlexical_seed.__file__).read_text("utf-8")
    for forbidden in ("EXP-", "benchmark", "private", *STRATEGIES):
        assert forbidden not in source, forbidden


# --- condiciones, recuperación por condición y agente ---------------------------------------------


def test_conditions_are_the_declared_table_and_campaign():
    assert CONDITIONS == {
        "A": ("NO_MEMORY", None),
        "B": ("TEXT_HISTORY", None),
        "C_L": ("ASSOCIATIVE_MEMORY", LEXICAL),
        "C_S": ("ASSOCIATIVE_MEMORY", TRACE),
    }
    assert DECISION_INPUTS == {"order": ["test-0", "RETRIEVE", "plan"], "reproduction": "test-0"}
    assert (AGENT_NAME, POLICY) == ("bounded-ast-repair-v1+trace-seed-v1", "trace-component-seed/v1")
    campaign = NONLEXICAL_SEED_CAMPAIGN
    assert campaign["name"] == "nonlexical-seed-v1" and campaign["agent"] == AGENT_NAME
    assert campaign["conditions"] == tuple(CONDITIONS)
    assert (campaign["seeds"], campaign["replicates"]) == (REFERENCE_CAMPAIGN["seeds"], 2)
    assert campaign["task_set"] == "misleading-v1"
    assert campaign["train"] + campaign["transfer"] == TASK_SETS["misleading-v1"]
    assert (len(campaign["train"]), len(campaign["transfer"])) == (3, 6)
    assert campaign["evidence_dir"] == "evidence/nonlexical-seed-v1"
    assert condition_of("C_S") == ("ASSOCIATIVE_MEMORY", TRACE)
    with pytest.raises(ValueError, match="condición de siembra desconocida"):
        condition_of("C")


LEXICAL_QUERY = "title of T-config context of T-config"


def test_controls_retrieve_as_the_default_agent_and_ignore_the_trace():
    memory = EvidenceMemory(MEMORY)
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    other = stderr(block(traceback([app("app/config.py")])))
    for condition in ("A", "B", "C_L"):
        mode, signal = CONDITIONS[condition]
        memories, paths, seeding = retrieve(memory, condition, LEXICAL_QUERY, text, FILES)
        assert (memories, paths) == memory.retrieve(LEXICAL_QUERY, mode)
        assert seeding == {
            "policy": POLICY,
            "signal": signal,
            "components": trace_components(text, FILES),  # registrada, no usada
            "seeds": None,
            "state": None,
            "lesson": None,
        }
        assert retrieve(memory, condition, LEXICAL_QUERY, other, FILES)[:2] == (memories, paths)
    assert [m["task"] for m in retrieve(memory, "C_L", LEXICAL_QUERY, text, FILES)[0]] == ["T-config"]
    assert len(retrieve(memory, "B", LEXICAL_QUERY, text, FILES)[0]) == 3
    assert retrieve(memory, "A", LEXICAL_QUERY, text, FILES)[0] == []


def test_the_new_condition_seeds_from_the_trace_and_has_no_lexical_fallback():
    memory = EvidenceMemory(MEMORY)
    text = stderr(block(traceback([app("app/api.py"), app("app/auth.py")])))
    memories, paths, seeding = retrieve(memory, "C_S", LEXICAL_QUERY, text, FILES)
    assert [m["task"] for m in memories] == ["T-auth"]  # la traza, no la consulta léxica (T-config)
    assert seeding == {**seeded_retrieval(MEMORY, text, FILES)[2], "signal": TRACE}
    assert retrieve(memory, "C_S", "another query entirely", text, FILES) == (memories, paths, seeding)
    silent = stderr(block(traceback([TEST_FRAME], "AssertionError: 1 != 2"), outcome="FAIL"))
    memories, paths, seeding = retrieve(memory, "C_S", LEXICAL_QUERY, silent, FILES)
    assert (memories, paths, seeding["state"]) == ([], [], EMPTY)  # la señal calla: no vuelve a H4


def test_retrieval_inputs_cover_what_each_retrieval_received():
    arguments = ("query text", "stderr text", ("app/b.py", "app/a.py"), "f" * 64)
    base = {"policy": POLICY}
    assert retrieval_inputs("A", *arguments) == {**base, "condition": "A", "signal": None}
    assert retrieval_inputs("B", *arguments) == {
        **base,
        "condition": "B",
        "signal": None,
        "memory_sha256": "f" * 64,
    }
    assert retrieval_inputs("C_L", *arguments) == {
        **base,
        "condition": "C_L",
        "signal": LEXICAL,
        "memory_sha256": "f" * 64,
        "query": "query text",
    }
    assert retrieval_inputs("C_S", *arguments) == {
        **base,
        "condition": "C_S",
        "signal": TRACE,
        "memory_sha256": "f" * 64,
        "stderr": "stderr text",
        "files": ["app/a.py", "app/b.py"],
    }


def test_the_opt_in_agent_plans_exactly_as_the_default_agent():
    task = {"title": "title of T-config", "context": "context of T-config"}
    lessons = MEMORY["lessons"]
    compared = 0
    for mode, seed, size in itertools.product(
        ("NO_MEMORY", "TEXT_HISTORY", "ASSOCIATIVE_MEMORY"), REFERENCE_CAMPAIGN["seeds"], range(4)
    ):
        for memories in itertools.permutations(lessons, size):
            view = AgentView(task, {}, tuple(memories), mode, seed)
            default = BoundedRepairAgent().plan(view)
            assert TraceSeedRepairAgent().plan(view) == {**default, "policy": POLICY}
            compared += 1
    assert compared == 3 * 6 * 16
    agent = TraceSeedRepairAgent()
    assert agent.name == AGENT_NAME and agent.seeds_retrieval is True
    for marker in ("reads_reproduction", "reads_failures", "failure_transfer"):
        assert not getattr(agent, marker, False)  # no recibe test-0: la señal entra en la recuperación
    assert not getattr(BoundedRepairAgent(), "seeds_retrieval", False)
    assert type(agent).change is BoundedRepairAgent.change
