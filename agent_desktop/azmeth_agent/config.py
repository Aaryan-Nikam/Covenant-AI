from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


DEFAULT_BLOCKED_MARKERS = (
    "captcha",
    "verify you are human",
    "two-factor",
    "2fa",
    "one-time code",
    "login",
    "sign in",
    "payment",
    "billing",
    "permission",
    "authorize",
    "integration",
    "upgrade",
    "subscription",
    "delete",
    "remove campaign",
    "campaign settings",
    "daily limit",
    "sequence settings",
    "edit sequence",
    "message copy",
)


@dataclass(frozen=True)
class WorkflowConfig:
    name: str
    start_url: str
    allowed_domains: tuple[str, ...]
    require_confirmation_before_submit: bool = False
    max_steps: int = 80
    max_run_seconds: int = 600
    blocked_screen_markers: tuple[str, ...] = DEFAULT_BLOCKED_MARKERS

    def validate_url(self) -> None:
        parsed = urlparse(self.start_url)
        if parsed.scheme != "https":
            raise ValueError(f"Workflow {self.name} must start from an https URL.")
        host = parsed.hostname or ""
        if not any(host == domain or host.endswith(f".{domain}") for domain in self.allowed_domains):
            raise ValueError(f"Workflow {self.name} start URL is outside allowed domains.")


@dataclass(frozen=True)
class AgentConfig:
    client_id: str
    chrome_profile_dir: Path
    downloads_dir: Path
    evidence_dir: Path
    run_log_dir: Path
    workflows: tuple[WorkflowConfig, ...] = field(default_factory=tuple)

    @staticmethod
    def from_yaml(path: Path) -> "AgentConfig":
        data = yaml.safe_load(path.read_text()) or {}
        workflows = tuple(
            WorkflowConfig(
                name=item["name"],
                start_url=item["start_url"],
                allowed_domains=tuple(item["allowed_domains"]),
                require_confirmation_before_submit=item.get(
                    "require_confirmation_before_submit",
                    True,
                ),
                max_steps=item.get("max_steps", 80),
                max_run_seconds=item.get("max_run_seconds", 600),
                blocked_screen_markers=tuple(
                    item.get("blocked_screen_markers", DEFAULT_BLOCKED_MARKERS)
                ),
            )
            for item in data.get("workflows", [])
        )
        config = AgentConfig(
            client_id=data["client_id"],
            chrome_profile_dir=Path(data["chrome_profile_dir"]).expanduser(),
            downloads_dir=Path(data["downloads_dir"]).expanduser(),
            evidence_dir=Path(data["evidence_dir"]).expanduser(),
            run_log_dir=Path(data["run_log_dir"]).expanduser(),
            workflows=workflows,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.client_id.strip():
            raise ValueError("client_id is required.")
        for workflow in self.workflows:
            workflow.validate_url()

    def workflow(self, name: str) -> WorkflowConfig:
        for workflow in self.workflows:
            if workflow.name == name:
                return workflow
        raise KeyError(f"Unknown workflow: {name}")


def redact_config(config: AgentConfig) -> dict[str, Any]:
    return {
        "client_id": config.client_id,
        "chrome_profile_dir": str(config.chrome_profile_dir),
        "downloads_dir": str(config.downloads_dir),
        "evidence_dir": str(config.evidence_dir),
        "run_log_dir": str(config.run_log_dir),
        "workflows": [workflow.name for workflow in config.workflows],
    }
