from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from azmeth_agent.actions import ActionRisk, ActionType, AgentAction
from azmeth_agent.llm import AgentBrain, AgentTask
from azmeth_agent.tools import Observation


class VisionModelClient(Protocol):
    def decide(self, prompt: str, screenshot_path: Path) -> str:
        ...


class JsonVisionBrain(AgentBrain):
    """Vision agent brain with a strict JSON action contract."""

    def __init__(self, model_client: VisionModelClient) -> None:
        self.model_client = model_client

    def next_action(
        self,
        task: AgentTask,
        observation: Observation,
        step_index: int,
        history: tuple[str, ...],
    ) -> AgentAction:
        prompt = self._build_prompt(task, observation, step_index, history)
        raw = self.model_client.decide(prompt, observation.screenshot_path)
        return parse_action_json(raw)

    @staticmethod
    def _build_prompt(
        task: AgentTask,
        observation: Observation,
        step_index: int,
        history: tuple[str, ...],
    ) -> str:
        return (
            "You are controlling a real user's visible browser through screenshot, mouse, "
            "keyboard, wait, scroll, and native file upload actions only. Do not use DOM, "
            "JavaScript, hidden selectors, browser devtools, internal APIs, or scraping.\n\n"
            "Return exactly one JSON object and no markdown.\n"
            "Allowed action_type values: screenshot, click, type_text, hotkey, scroll, wait, "
            "upload_file, complete, escalate.\n"
            "Allowed risk values: low, final_submit.\n"
            "Use risk=final_submit for any click/key action that completes the CSV import or "
            "performs another final irreversible step. The policy may allow configured imports, "
            "but will still block settings, billing, permissions, deletion, or ambiguous account changes.\n"
            "Escalate if you see login, 2FA, CAPTCHA, billing, permission, destructive actions, "
            "campaign settings, sequence editing, daily limits, ambiguous campaign choice, "
            "unclear field mapping, or any screen outside the task.\n\n"
            f"Task: {json.dumps(asdict(task), sort_keys=True)}\n"
            f"Current URL if known: {observation.current_url}\n"
            f"Step index: {step_index}\n"
            f"Recent history: {json.dumps(history[-10:])}\n\n"
            "JSON schema:\n"
            '{"action_type":"click","reason":"short reason","risk":"low","x":100,"y":100,'
            '"text":null,"keys":[],"amount":null,"seconds":null,"path":null,"message":null}'
        )


def parse_action_json(raw: str) -> AgentAction:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return AgentAction.escalate("invalid model JSON", f"Model returned invalid JSON: {exc}")

    try:
        action_type = ActionType(data["action_type"])
        risk = ActionRisk(data.get("risk", ActionRisk.LOW.value))
    except (KeyError, ValueError) as exc:
        return AgentAction.escalate("invalid model action", f"Model returned invalid action: {exc}")

    path = data.get("path")
    return AgentAction(
        action_type=action_type,
        reason=str(data.get("reason") or "no reason provided"),
        risk=risk,
        x=data.get("x"),
        y=data.get("y"),
        text=data.get("text"),
        keys=tuple(data.get("keys") or ()),
        amount=data.get("amount"),
        seconds=data.get("seconds"),
        path=Path(path) if path else None,
        message=data.get("message"),
    )
