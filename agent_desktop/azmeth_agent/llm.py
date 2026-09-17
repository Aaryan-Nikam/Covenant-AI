from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from azmeth_agent.actions import AgentAction
from azmeth_agent.tools import Observation


@dataclass(frozen=True)
class AgentTask:
    name: str
    goal: str
    success_criteria: tuple[str, ...]
    cautions: tuple[str, ...]


class AgentBrain(Protocol):
    def next_action(
        self,
        task: AgentTask,
        observation: Observation,
        step_index: int,
        history: tuple[str, ...],
    ) -> AgentAction:
        ...


class ScriptedBrain:
    """Deterministic brain for tests and first-run dry runs."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = actions

    def next_action(
        self,
        task: AgentTask,
        observation: Observation,
        step_index: int,
        history: tuple[str, ...],
    ) -> AgentAction:
        if step_index >= len(self.actions):
            return AgentAction.escalate(
                "script exhausted",
                f"No scripted action available for task {task.name}.",
            )
        return self.actions[step_index]
