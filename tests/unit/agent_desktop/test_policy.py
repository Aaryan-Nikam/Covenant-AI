from __future__ import annotations

from pathlib import Path

from azmeth_agent.actions import ActionRisk, ActionType, AgentAction
from azmeth_agent.config import WorkflowConfig
from azmeth_agent.policy import SafetyPolicy


def _workflow() -> WorkflowConfig:
    return WorkflowConfig(
        name="dripify_csv_upload",
        start_url="https://app.dripify.io/",
        allowed_domains=("dripify.io",),
    )


def test_policy_allows_csv_upload(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text("name,email\nJane,jane@example.com\n", encoding="utf-8")

    decision = SafetyPolicy(_workflow()).check_action(
        AgentAction(
            action_type=ActionType.UPLOAD_FILE,
            reason="select generated import file",
            path=csv_path,
        ),
        current_url="https://app.dripify.io/campaigns",
    )

    assert decision.allowed is True


def test_policy_blocks_non_csv_upload(tmp_path: Path) -> None:
    txt_path = tmp_path / "leads.txt"
    txt_path.write_text("not a csv", encoding="utf-8")

    decision = SafetyPolicy(_workflow()).check_action(
        AgentAction(
            action_type=ActionType.UPLOAD_FILE,
            reason="select generated import file",
            path=txt_path,
        ),
        current_url="https://app.dripify.io/campaigns",
    )

    assert decision.allowed is False
    assert "CSV" in decision.reason


def test_policy_blocks_outside_domain() -> None:
    decision = SafetyPolicy(_workflow()).check_action(
        AgentAction(action_type=ActionType.CLICK, reason="click visible button", x=10, y=20),
        current_url="https://evil.example.com/login",
    )

    assert decision.allowed is False
    assert "outside allowlist" in decision.reason


def test_policy_blocks_sensitive_screen_marker() -> None:
    decision = SafetyPolicy(_workflow()).check_screen_text("Please enter your 2FA one-time code")

    assert decision.allowed is False
    assert "2fa" in decision.reason.casefold()


def test_policy_blocks_final_submit_without_confirmation() -> None:
    workflow = WorkflowConfig(
        name="dripify_csv_upload",
        start_url="https://app.dripify.io/",
        allowed_domains=("dripify.io",),
        require_confirmation_before_submit=True,
    )
    decision = SafetyPolicy(workflow).check_action(
        AgentAction(
            action_type=ActionType.CLICK,
            reason="click final import submit button",
            risk=ActionRisk.FINAL_SUBMIT,
            x=100,
            y=200,
        ),
        current_url="https://app.dripify.io/campaigns",
    )

    assert decision.allowed is False
    assert "confirmation" in decision.reason.casefold()


def test_policy_allows_final_submit_by_default_for_configured_import() -> None:
    decision = SafetyPolicy(_workflow()).check_action(
        AgentAction(
            action_type=ActionType.CLICK,
            reason="click final import submit button",
            risk=ActionRisk.FINAL_SUBMIT,
            x=100,
            y=200,
        ),
        current_url="https://app.dripify.io/campaigns",
    )

    assert decision.allowed is True


def test_policy_blocks_campaign_settings_screen() -> None:
    decision = SafetyPolicy(_workflow()).check_screen_text("Campaign settings daily limit")

    assert decision.allowed is False
    assert "campaign settings" in decision.reason.casefold()
