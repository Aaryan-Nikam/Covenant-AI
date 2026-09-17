from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ActionType(StrEnum):
    SCREENSHOT = "screenshot"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    WAIT = "wait"
    UPLOAD_FILE = "upload_file"
    COMPLETE = "complete"
    ESCALATE = "escalate"


class ActionRisk(StrEnum):
    LOW = "low"
    FINAL_SUBMIT = "final_submit"


@dataclass(frozen=True)
class AgentAction:
    action_type: ActionType
    reason: str
    risk: ActionRisk = ActionRisk.LOW
    x: int | None = None
    y: int | None = None
    text: str | None = None
    keys: tuple[str, ...] = ()
    amount: int | None = None
    seconds: float | None = None
    path: Path | None = None
    message: str | None = None

    @staticmethod
    def screenshot(reason: str = "observe current state") -> "AgentAction":
        return AgentAction(action_type=ActionType.SCREENSHOT, reason=reason)

    @staticmethod
    def complete(reason: str, message: str) -> "AgentAction":
        return AgentAction(action_type=ActionType.COMPLETE, reason=reason, message=message)

    @staticmethod
    def escalate(reason: str, message: str) -> "AgentAction":
        return AgentAction(action_type=ActionType.ESCALATE, reason=reason, message=message)
