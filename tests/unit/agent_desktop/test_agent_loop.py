from __future__ import annotations

from pathlib import Path

from azmeth_agent.actions import AgentAction
from azmeth_agent.agent_loop import AgentLoop
from azmeth_agent.config import WorkflowConfig
from azmeth_agent.llm import ScriptedBrain
from azmeth_agent.logging import RunLedger
from azmeth_agent.policy import SafetyPolicy
from azmeth_agent.tools import DryRunTools
from azmeth_agent.workflows import build_dripify_upload_task


def _workflow() -> WorkflowConfig:
    return WorkflowConfig(
        name="dripify_csv_upload",
        start_url="https://app.dripify.io/",
        allowed_domains=("dripify.io",),
        max_steps=3,
    )


def test_agent_loop_completes_scripted_run(tmp_path: Path) -> None:
    workflow = _workflow()
    tools = DryRunTools(tmp_path / "evidence")
    ledger = RunLedger(tmp_path / "logs", secret="test-secret", run_id="run-1")
    brain = ScriptedBrain([AgentAction.complete("success visible", "Import completed.")])
    loop = AgentLoop(workflow, SafetyPolicy(workflow), tools, brain, ledger)

    result = loop.run(build_dripify_upload_task(tmp_path / "leads.csv"))

    assert result == "Import completed."
    assert "open_url:https://app.dripify.io/" in tools.actions
    log_text = ledger.path.read_text(encoding="utf-8")
    assert "run_started" in log_text
    assert "run_completed" in log_text


def test_agent_loop_escalates_blocked_screen(tmp_path: Path) -> None:
    workflow = _workflow()
    tools = DryRunTools(tmp_path / "evidence")
    tools.observation_text = "Sign in to continue"
    ledger = RunLedger(tmp_path / "logs", secret="test-secret", run_id="run-2")
    brain = ScriptedBrain([AgentAction.complete("success visible", "Import completed.")])
    loop = AgentLoop(workflow, SafetyPolicy(workflow), tools, brain, ledger)

    result = loop.run(build_dripify_upload_task(tmp_path / "leads.csv"))

    assert "login" in result.casefold() or "sign in" in result.casefold()
    assert any(action.startswith("notify_human:") for action in tools.actions)
    assert "run_escalated" in ledger.path.read_text(encoding="utf-8")
