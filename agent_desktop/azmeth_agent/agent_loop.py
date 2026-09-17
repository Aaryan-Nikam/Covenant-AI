from __future__ import annotations

import time
from dataclasses import asdict

from azmeth_agent.actions import ActionType, AgentAction
from azmeth_agent.config import WorkflowConfig
from azmeth_agent.llm import AgentBrain, AgentTask
from azmeth_agent.logging import RunLedger
from azmeth_agent.policy import SafetyPolicy
from azmeth_agent.tools import DesktopTools, Observation


class AgentLoop:
    def __init__(
        self,
        workflow: WorkflowConfig,
        policy: SafetyPolicy,
        tools: DesktopTools,
        brain: AgentBrain,
        ledger: RunLedger,
    ) -> None:
        self.workflow = workflow
        self.policy = policy
        self.tools = tools
        self.brain = brain
        self.ledger = ledger

    def run(self, task: AgentTask) -> str:
        self.ledger.append(
            "run_started",
            {
                "workflow": self.workflow.name,
                "task": asdict(task),
                "start_url": self.workflow.start_url,
            },
        )
        self.tools.open_url(self.workflow.start_url)
        started_at = time.monotonic()
        history: list[str] = []

        for step_index in range(self.workflow.max_steps):
            if time.monotonic() - started_at > self.workflow.max_run_seconds:
                return self._escalate("Time limit reached.")

            observation = self._observe(step_index)
            screen_decision = self.policy.check_screen_text(observation.screen_text)
            if not screen_decision.allowed:
                return self._escalate(screen_decision.reason)

            action = self.brain.next_action(task, observation, step_index, tuple(history))
            self.ledger.append(
                "action_proposed",
                {
                    "step": step_index,
                    "action": self._action_payload(action),
                    "current_url": observation.current_url,
                },
            )

            decision = self.policy.check_action(action, current_url=observation.current_url)
            if not decision.allowed:
                return self._escalate(decision.reason)

            if action.action_type == ActionType.COMPLETE:
                message = action.message or "Task completed."
                self.ledger.append("run_completed", {"message": message})
                return message

            if action.action_type == ActionType.ESCALATE:
                return self._escalate(action.message or action.reason)

            self._execute(action)
            history.append(f"{action.action_type.value}: {action.reason}")

        return self._escalate("Step limit reached.")

    def _observe(self, step_index: int) -> Observation:
        observation = self.tools.observe()
        self.ledger.append(
            "observation",
            {
                "step": step_index,
                "screenshot_path": str(observation.screenshot_path),
                "screen_text": observation.screen_text[:2_000],
                "current_url": observation.current_url,
            },
        )
        return observation

    def _execute(self, action: AgentAction) -> None:
        if action.action_type == ActionType.SCREENSHOT:
            self.tools.observe()
        elif action.action_type == ActionType.CLICK:
            self.tools.click(action.x or 0, action.y or 0)
        elif action.action_type == ActionType.TYPE_TEXT:
            self.tools.type_text(action.text or "")
        elif action.action_type == ActionType.HOTKEY:
            self.tools.hotkey(action.keys)
        elif action.action_type == ActionType.SCROLL:
            self.tools.scroll(action.amount or 0)
        elif action.action_type == ActionType.WAIT:
            self.tools.wait(action.seconds or 1)
        elif action.action_type == ActionType.UPLOAD_FILE:
            if action.path is None:
                raise ValueError("upload_file action missing path")
            self.tools.upload_file(action.path)
        self.ledger.append("action_executed", {"action": self._action_payload(action)})

    def _escalate(self, message: str) -> str:
        self.tools.notify_human(message)
        self.ledger.append("run_escalated", {"message": message})
        return message

    @staticmethod
    def _action_payload(action: AgentAction) -> dict[str, object]:
        return {
            "action_type": action.action_type.value,
            "reason": action.reason,
            "risk": action.risk.value,
            "x": action.x,
            "y": action.y,
            "text": action.text,
            "keys": action.keys,
            "amount": action.amount,
            "seconds": action.seconds,
            "path": str(action.path) if action.path else None,
            "message": action.message,
        }
