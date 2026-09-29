"""A bounded, deterministic program-repair agent, not an autonomous LLM.

The agent has generic repair operators, never a task-id -> solution lookup.
No benchmark/private import or filesystem access: the runner supplies public
task text, current source strings and eligible memories through AgentView.
Operators and the initial random prior are experimental assumptions to audit.
"""

import ast
import random
from dataclasses import dataclass

from associative_agent_loop.memory.text import cosine_similarity

STRATEGIES = (
    "validate_optional_identity",
    "normalize_environment",
    "initialize_storage",
)
RULES = {
    "validate_optional_identity": (
        "Validate an optional identity before accessing its fields; preserve valid identities."
    ),
    "normalize_environment": (
        "Resolve missing or empty environment values using the component's declared default "
        "before using them."
    ),
    "initialize_storage": (
        "Initialize storage before the first dependent operation, including background entry points."
    ),
}


def prior_order(seed: int) -> tuple[str, ...]:
    """The no-memory strategy prior: a seeded permutation of STRATEGIES.

    Single source of truth for the agent and for the campaign-coverage test (#44).
    """
    prior = list(STRATEGIES)
    random.Random(seed).shuffle(prior)
    return tuple(prior)


@dataclass(frozen=True)
class AgentView:
    task: dict
    files: dict[str, str]
    memories: tuple[dict, ...]
    memory_mode: str
    seed: int


class BoundedRepairAgent:
    name = "bounded-ast-repair-v1"

    def plan(self, view: AgentView):
        prior = list(prior_order(view.seed))
        memories = list(view.memories)
        if view.memory_mode == "TEXT_HISTORY":
            query = view.task["title"] + " " + view.task["context"]
            memories.sort(key=lambda m: -cosine_similarity(query, m["symptom"] + " " + m["rule"]))
        selected = next((m for m in memories if m["strategy"] in prior), None)
        plan = (
            ([selected["strategy"]] + [s for s in prior if s != selected["strategy"]])
            if selected
            else prior[:]
        )
        return {
            "considered": prior,
            "selected": plan[0],
            "plan": plan,
            "without_memory": prior[0],
            "influenced_by_memory": bool(selected and plan != prior),
            "memory_ids": [selected["id"]] if selected else [],
            "initial_hypothesis": RULES[plan[0]],
        }

    def change(self, files: dict[str, str], strategy: str, seed: int):
        ordered = sorted(files)
        random.Random(seed).shuffle(ordered)
        # File priority follows the selected strategy, without task identifiers.
        words = {
            "validate_optional_identity": ("USERS",),
            "normalize_environment": ("os.getenv",),
            "initialize_storage": ("Database()",),
        }[strategy]
        ordered.sort(key=lambda p: not any(w in files[p] for w in words))
        inspected = []
        for path in ordered:
            inspected.append(path)
            source = files[path]
            tree = ast.parse(source)
            lines = source.splitlines(keepends=True)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = ast.get_source_segment(source, node) or ""
                if strategy == "validate_optional_identity" and "Unauthorized" in source:
                    for stmt in node.body:
                        if (
                            isinstance(stmt, ast.Assign)
                            and isinstance(stmt.value, ast.Call)
                            and isinstance(stmt.value.func, ast.Attribute)
                            and ast.unparse(stmt.value.func) == "USERS.get"
                        ):
                            name = ast.unparse(stmt.targets[0])
                            if f"if {name} is None:" not in body:
                                indent = " " * stmt.col_offset
                                lines.insert(
                                    stmt.end_lineno,
                                    f"{indent}if {name} is None:\n"
                                    f'{indent}    raise Unauthorized("authentication required")\n',
                                )
                                return path, "".join(lines), inspected
                elif strategy == "normalize_environment":
                    defaults = [
                        n.targets[0].id
                        for n in tree.body
                        if isinstance(n, ast.Assign)
                        and isinstance(n.targets[0], ast.Name)
                        and n.targets[0].id.startswith("DEFAULT_")
                    ]
                    for stmt in node.body:
                        if (
                            defaults
                            and isinstance(stmt, ast.Assign)
                            and isinstance(stmt.value, ast.Call)
                            and ast.unparse(stmt.value.func) == "os.getenv"
                        ):
                            line = lines[stmt.lineno - 1]
                            lines[stmt.lineno - 1] = line.rstrip("\r\n") + " or " + defaults[0] + "\n"
                            return path, "".join(lines), inspected
                elif strategy == "initialize_storage":
                    if (
                        node.name == "start"
                        and "self.database.execute" in body
                        and "self.database.initialize()" not in body
                    ):
                        lines.insert(
                            node.body[0].lineno - 1,
                            " " * node.body[0].col_offset + "self.database.initialize()\n",
                        )
                        return path, "".join(lines), inspected
                    for stmt in node.body:
                        if (
                            isinstance(stmt, ast.Assign)
                            and isinstance(stmt.targets[0], ast.Name)
                            and isinstance(stmt.value, ast.Call)
                            and ast.unparse(stmt.value.func) == "Database"
                        ):
                            name = ast.unparse(stmt.targets[0])
                            if f"{name}.initialize()" not in body:
                                lines.insert(
                                    stmt.end_lineno,
                                    " " * stmt.col_offset + name + ".initialize()\n",
                                )
                                return path, "".join(lines), inspected
        return None, None, inspected
