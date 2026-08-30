from __future__ import annotations

import pytest

from office_runtime.ops.repo_health.plugin_loader import validate_discovered_plugin
from office_runtime.ops.repo_health.plugins.base import BasePlugin, PluginCapability


class ExamplePlugin(BasePlugin):
    name = "example"
    version = "2.1.0"
    capability = PluginCapability.REMOTE_READ

    def run(self, ctx):
        return {"status": "PASS", "message": "ok"}


class MalformedPlugin(ExamplePlugin):
    def capability_descriptor(self):
        return {
            "capability_id": "repo_health.bad@1",
            "inputs": ["repo_health.context@1"],
            "outputs": ["repo_health.plugin-result@1"],
            "side_effects": "",
            "failure_behavior": "return normalized result",
            "evidence": ["result.evidence"],
        }


def test_descriptor_exposes_execution_boundary_metadata():
    descriptor = ExamplePlugin().capability_descriptor()

    assert descriptor == {
        "capability_id": "repo_health.example@2.1.0",
        "inputs": ["repo_health.context@1"],
        "outputs": ["repo_health.plugin-result@1"],
        "side_effects": "remote read-only; no remote mutation authority",
        "failure_behavior": (
            "return a normalized PASS/FAIL/WARN/NA/ERROR result; "
            "malformed plugin output is system_error"
        ),
        "evidence": ["result.evidence", "result.meta"],
    }


def test_discovery_boundary_rejects_incomplete_descriptor():
    plugin = MalformedPlugin()

    with pytest.raises(ValueError, match="side_effects"):
        BasePlugin.validate_capability_descriptor(plugin.capability_descriptor())


def test_discovery_boundary_accepts_complete_descriptor():
    plugin = ExamplePlugin()

    assert validate_discovered_plugin(plugin) is plugin
