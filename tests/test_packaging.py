"""Empaquetado, configuración y persistencia (#9)."""

import json
import os
from importlib.metadata import entry_points

import pytest
from pydantic import ValidationError

import associative_agent_loop as aal
from associative_agent_loop import Agent, JsonGraphStore, MemoryGraph, load_config
from associative_agent_loop.agent.tools import weather_scenario
from associative_agent_loop.memory import fsutil


def test_public_api_and_version():
    assert aal.__version__
    for name in ("Agent", "MemoryGraph", "Retriever", "Consolidator", "load_config", "JsonGraphStore"):
        assert hasattr(aal, name)


def test_cli_entry_point_is_registered():
    scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert scripts.get("aal-benchmark") == "associative_agent_loop.main:main"


def test_config_defaults_toml_and_env_precedence(tmp_path):
    assert load_config(environ={}).retrieval.damping == 0.7

    toml = tmp_path / "aal.toml"
    toml.write_text(
        "[agent]\nmax_attempts = 2\n\n[retrieval]\ndamping = 0.5\nfan_out = \"linear\"\n"
        "\n[consolidation]\nmax_edges = 100\n",
        "utf-8",
    )
    cfg = load_config(toml, environ={"AAL_RETRIEVAL__DAMPING": "0.6", "OTHER": "x"})
    assert cfg.agent.max_attempts == 2
    assert cfg.retrieval.fan_out == "linear"
    assert cfg.retrieval.damping == 0.6  # el entorno gana al archivo
    assert cfg.consolidation.max_edges == 100


def test_config_is_validated(tmp_path):
    with pytest.raises(ValidationError):
        load_config(environ={"AAL_RETRIEVAL__DAMPING": "1.5"})
    bad = tmp_path / "bad.toml"
    bad.write_text("[agent]\nunknown_option = 1\n", "utf-8")
    with pytest.raises(ValidationError):
        load_config(bad, environ={})


def test_agent_from_config_applies_every_section():
    cfg = load_config(
        environ={
            "AAL_AGENT__MAX_ATTEMPTS": "1",
            "AAL_AGENT__DECAY_RATE": "0.2",
            "AAL_RETRIEVAL__FAN_OUT": "none",
            "AAL_CONSOLIDATION__HEBBIAN_RATE": "0.9",
        }
    )
    agent = Agent.from_config(weather_scenario(), cfg)
    assert agent.max_attempts == 1
    assert agent.memory.decay_rate == 0.2
    assert agent.retriever.config.fan_out == "none"
    assert agent.consolidator.hebbian_rate == 0.9
    ep = agent.run("clima en Santiago")
    assert ep.attempts == 1 and not ep.success  # max_attempts=1: solo prueba v1


def test_json_store_roundtrip(tmp_path):
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    store = JsonGraphStore(tmp_path / "sub" / "memory.json")
    assert not store.exists()
    assert len(store.load_or_new()) == 0
    store.save(agent.memory)
    assert store.load().to_dict() == agent.memory.to_dict()


def test_atomic_write_keeps_previous_file_if_interrupted(tmp_path, monkeypatch):
    path = tmp_path / "memory.json"
    MemoryGraph().save(path)
    original = path.read_text("utf-8")

    def boom(src, dst):
        raise OSError("disco lleno")

    monkeypatch.setattr(fsutil.os, "replace", boom)
    agent = Agent(weather_scenario())
    agent.run("clima en Santiago")
    with pytest.raises(OSError):
        agent.memory.save(path)
    assert path.read_text("utf-8") == original  # intacto, no truncado
    assert json.loads(original)["schema_version"] == 2
    assert [p.name for p in tmp_path.iterdir()] == ["memory.json"]  # sin temporales huérfanos
    assert os.path.exists(path)
