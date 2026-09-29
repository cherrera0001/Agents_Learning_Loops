"""Versioned contracts; Experiment 0's schema_version=2 is unchanged."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemoryMode(StrEnum):
    NO_MEMORY = "NO_MEMORY"
    TEXT_HISTORY = "TEXT_HISTORY"
    ASSOCIATIVE_MEMORY = "ASSOCIATIVE_MEMORY"


class PublicTask(StrictModel):
    id: str
    title: str
    context: str
    expected: str
    observed: str
    acceptance_criteria: str
    reproduction: str
    test_file: str

    def query(self):
        return self.title + " " + self.context


class Reflection(StrictModel):
    goal: str
    expected: str
    observed: str
    root_cause: str | None
    evidence: list[str]
    failed_strategy: list[str]
    successful_strategy: str | None
    generalizable_rule: str | None
    confidence: float = Field(ge=0, le=1)
    memory_action: Literal["ADD", "UPDATE", "MERGE", "IGNORE", "DEPRECATE"]

    @model_validator(mode="after")
    def evidence_required(self):
        if self.memory_action != "IGNORE" and not self.evidence:
            raise ValueError("A reflection is not evidence: references are required")
        return self


class KnowledgeNode(StrictModel):
    id: str
    type: Literal[
        "Task",
        "Experience",
        "Symptom",
        "Cause",
        "Strategy",
        "Evidence",
        "Lesson",
        "Component",
        "Skill",
    ]
    label: str
    evidence: list[str] = Field(default_factory=list)


class KnowledgeEdge(StrictModel):
    source: str
    target: str
    relation: Literal[
        "caused_by",
        "solved_by",
        "contradicts",
        "evidence_for",
        "related_to",
        "applies_to",
        "promoted_to_skill",
    ]


class LessonRecord(StrictModel):
    id: str
    run_id: str
    task: str
    symptom: str
    strategy: str
    rule: str
    evidence: list[str] = Field(min_length=1)
    receipt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MemoryDocument(StrictModel):
    schema_id: Literal["software-learning-memory/v1"] = "software-learning-memory/v1"
    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)
    lessons: list[LessonRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_graph(self):
        ids = {n.id for n in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("duplicate node ids")
        if any(e.source not in ids or e.target not in ids for e in self.edges):
            raise ValueError("dangling edge")
        if any(lesson.id not in ids for lesson in self.lessons):
            raise ValueError("lesson missing graph node")
        return self
