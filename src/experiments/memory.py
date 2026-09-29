"""Evidence-grounded typed graph projected onto Experiment 0 propagation.

Projection is read-only and ephemeral. Old graph files/APIs are never migrated
implicitly. Retrieval uses lexical seeding and the existing refractory,
fan-out-normalized spreading activation, not vector-memory condition D/E.
"""

from associative_agent_loop.memory.associative import RetrievalConfig, Retriever
from associative_agent_loop.memory.graph import EdgeType, MemoryGraph, NodeType
from associative_agent_loop.memory.text import cosine_similarity

from .evidence import digest, read_receipt
from .models import KnowledgeEdge, KnowledgeNode, MemoryDocument, Reflection


class EvidenceMemory:
    def __init__(self, document=None):
        self.document = MemoryDocument.model_validate(document or {})

    def snapshot(self):
        return self.document.model_dump(mode="json")

    @property
    def lessons(self):
        return [lesson.model_dump(mode="json") for lesson in self.document.lessons]

    def retrieve(self, query, mode):
        if mode == "NO_MEMORY":
            return [], []
        if mode == "TEXT_HISTORY":
            return self.lessons, []
        if mode != "ASSOCIATIVE_MEMORY":
            raise ValueError(mode)
        projection = MemoryGraph(decay_rate=0)
        for n in self.document.nodes:
            projection.add_node("concept:" + n.id, NodeType.CONCEPT, n.label)
        for e in self.document.edges:
            # Causal direction remains in typed graph; this projection uses
            # undirected associative traversal only, not proof of causality.
            projection.add_edge(
                "concept:" + e.source,
                "concept:" + e.target,
                EdgeType.ASSOCIATED_WITH,
                weight=0.7,
            )
        seeds = {}
        for n in self.document.nodes:
            if n.type in ("Symptom", "Component", "Lesson"):
                score = cosine_similarity(query, n.label)
                if score >= 0.12:
                    seeds["concept:" + n.id] = score
        retriever = Retriever(projection, config=RetrievalConfig(max_hops=5, firing_threshold=0.001))
        trace = retriever.spread_trace(seeds)
        ranked = sorted(
            self.lessons,
            key=lambda m: (-trace.activation.get("concept:" + m["id"], 0), m["task"], m["strategy"]),
        )
        ranked = [m for m in ranked if trace.activation.get("concept:" + m["id"], 0) >= 0.005][:1]
        paths = [
            {
                "memory": m["id"],
                "activation": trace.activation["concept:" + m["id"]],
                "path": [s.removeprefix("concept:") for s in trace.path_to("concept:" + m["id"])],
                "evidence": m["evidence"],
            }
            for m in ranked
        ]
        return [dict(m) for m in ranked], paths

    def consolidate(self, receipt_path):
        receipt = read_receipt(receipt_path)
        reflection = Reflection.model_validate(receipt["reflection"])
        if reflection.memory_action == "IGNORE":
            return []
        # v1 implements ADD / IGNORE only. Unsupported intentions must fail,
        # never silently turn MERGE or DEPRECATE into ADD.
        if reflection.memory_action != "ADD":
            raise NotImplementedError(reflection.memory_action)
        if receipt["split"] != "train":
            raise ValueError("evaluation memory is frozen")
        if receipt["result"] != "PASS" or not reflection.successful_strategy:
            raise ValueError("unverified strategy cannot become a lesson")
        known_refs = {t["id"] for t in receipt["tests"]}
        if not set(reflection.evidence) <= known_refs:
            raise ValueError("reflection references missing evidence")
        passed = [t for t in receipt["tests"] if t["returncode"] == 0]
        if not passed or passed[-1]["id"] not in reflection.evidence:
            raise ValueError("reflection must reference passing test evidence")
        if (
            receipt["tests"][0]["returncode"] == 0
            or receipt["tests"][-1]["returncode"] != 0
            or not receipt["actions"][-1]["patch"]
            or receipt["actions"][-1]["strategy"] != reflection.successful_strategy
        ):
            raise ValueError("reflection is inconsistent with observed intervention")
        run = receipt["run_id"]
        if any(m["run_id"] == run for m in self.lessons):
            return []
        key = "lesson:" + run
        refs = [run + "#" + r for r in reflection.evidence]
        lesson = {
            "id": key,
            "run_id": run,
            "task": receipt["task"]["id"],
            "symptom": receipt["task"]["title"] + " " + receipt["task"]["context"],
            "strategy": reflection.successful_strategy,
            "rule": reflection.generalizable_rule,
            "evidence": refs,
            "receipt_sha256": receipt["receipt_sha256"],
        }
        nodes = list(self.document.nodes)
        edges = list(self.document.edges)
        types = {
            "Task": receipt["task"]["title"],
            "Experience": run,
            "Symptom": lesson["symptom"],
            "Cause": reflection.root_cause or "unconfirmed",
            "Strategy": lesson["strategy"],
            "Evidence": refs[-1],
            "Lesson": lesson["rule"],
            "Component": " ".join(receipt["actions"][-1]["changed_files"]),
        }
        ids = {t: key if t == "Lesson" else t.lower() + ":" + run for t in types}
        for t, label in types.items():
            nodes.append(KnowledgeNode(id=ids[t], type=t, label=label, evidence=refs))
        for src, dst, relation in [
            ("Task", "Experience", "related_to"),
            ("Symptom", "Task", "related_to"),
            ("Experience", "Lesson", "related_to"),
            ("Symptom", "Cause", "caused_by"),
            ("Cause", "Strategy", "solved_by"),
            ("Evidence", "Lesson", "evidence_for"),
            ("Lesson", "Strategy", "related_to"),
            ("Lesson", "Component", "applies_to"),
        ]:
            edges.append(KnowledgeEdge(source=ids[src], target=ids[dst], relation=relation))
        self.document = MemoryDocument(nodes=nodes, edges=edges, lessons=[*self.lessons, lesson])
        return [{"action": "ADD", "memory": key, "evidence": refs}]

    def fingerprint(self):
        return digest(self.snapshot())
