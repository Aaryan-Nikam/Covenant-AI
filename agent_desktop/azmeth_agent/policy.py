from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from azmeth_agent.actions import ActionRisk, ActionType, AgentAction
from azmeth_agent.config import WorkflowConfig


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class SafetyPolicy:
    def __init__(self, workflow: WorkflowConfig, max_csv_bytes: int = 10_000_000) -> None:
        self.workflow = workflow
        self.max_csv_bytes = max_csv_bytes

    def check_action(self, action: AgentAction, current_url: str | None = None) -> PolicyDecision:
        if action.action_type in {ActionType.COMPLETE, ActionType.ESCALATE, ActionType.SCREENSHOT}:
            return PolicyDecision(True, "terminal or observation action")

        if (
            self.workflow.require_confirmation_before_submit
            and action.risk == ActionRisk.FINAL_SUBMIT
        ):
            return PolicyDecision(
                False,
                "Final submission requires human confirmation for this workflow.",
            )

        if current_url and not self._url_allowed(current_url):
            return PolicyDecision(False, f"Current URL is outside allowlist: {current_url}")

        if action.action_type == ActionType.UPLOAD_FILE:
            if action.path is None:
                return PolicyDecision(False, "Upload action is missing a file path.")
            return self.check_upload_file(action.path)

        if action.action_type == ActionType.CLICK and (action.x is None or action.y is None):
            return PolicyDecision(False, "Click action requires x and y coordinates.")

        if action.action_type == ActionType.TYPE_TEXT and action.text is None:
            return PolicyDecision(False, "Type action requires text.")

        if action.action_type == ActionType.HOTKEY and not action.keys:
            return PolicyDecision(False, "Hotkey action requires keys.")

        return PolicyDecision(True, "action allowed")

    def check_screen_text(self, screen_text: str) -> PolicyDecision:
        normalized = screen_text.casefold()
        for marker in self.workflow.blocked_screen_markers:
            if marker.casefold() in normalized:
                return PolicyDecision(False, f"Blocked screen marker detected: {marker}")
        return PolicyDecision(True, "screen text allowed")

    def check_upload_file(self, path: Path) -> PolicyDecision:
        if path.suffix.casefold() != ".csv":
            return PolicyDecision(False, "Only CSV uploads are allowed.")
        if not path.exists():
            return PolicyDecision(False, f"CSV file does not exist: {path}")
        if path.stat().st_size > self.max_csv_bytes:
            return PolicyDecision(False, "CSV exceeds configured size limit.")
        return PolicyDecision(True, "CSV upload allowed")

    def _url_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = parsed.hostname or ""
        return any(host == domain or host.endswith(f".{domain}") for domain in self.workflow.allowed_domains)
