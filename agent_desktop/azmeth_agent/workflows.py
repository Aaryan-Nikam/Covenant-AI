from __future__ import annotations

from pathlib import Path

from azmeth_agent.llm import AgentTask
from azmeth_agent.policy import SafetyPolicy


def build_dripify_upload_task(csv_path: Path, campaign_hint: str | None = None) -> AgentTask:
    campaign_text = campaign_hint or "the configured target campaign"
    return AgentTask(
        name="dripify_csv_upload",
        goal=(
            "Upload the prepared CSV file into Dripify using the visible browser UI. "
            f"Target campaign: {campaign_text}. CSV path: {csv_path}."
        ),
        success_criteria=(
            "The CSV file has been selected in Dripify's import flow.",
            "Fields are mapped only when the mapping is obvious from visible labels.",
            "The import confirmation/success screen is visible.",
            "No LinkedIn, billing, login, 2FA, CAPTCHA, or permission screen was bypassed.",
        ),
        cautions=(
            "Do not use hidden DOM selectors or browser-internal APIs to manipulate Dripify.",
            "Complete the configured CSV import flow when the target campaign is clear.",
            "Do not change campaign settings, daily limits, sequence messages, billing, or integrations.",
            "Escalate if the campaign choice is ambiguous or the screen asks for account-level changes.",
        ),
    )


def build_dripify_policy(workflow) -> SafetyPolicy:
    return SafetyPolicy(workflow)
