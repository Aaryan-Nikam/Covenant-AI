from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Observation:
    screenshot_path: Path
    screen_text: str
    current_url: str | None = None


class DesktopTools(Protocol):
    """DOM-free browser/desktop controls used by the agent loop."""

    def open_url(self, url: str) -> None:
        ...

    def observe(self) -> Observation:
        ...

    def click(self, x: int, y: int) -> None:
        ...

    def type_text(self, text: str) -> None:
        ...

    def hotkey(self, keys: tuple[str, ...]) -> None:
        ...

    def scroll(self, amount: int) -> None:
        ...

    def wait(self, seconds: float) -> None:
        ...

    def upload_file(self, path: Path) -> None:
        ...

    def notify_human(self, message: str) -> None:
        ...


class DryRunTools:
    """Safe test adapter that records actions without controlling the machine."""

    def __init__(self, evidence_dir: Path, current_url: str | None = None) -> None:
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.current_url = current_url
        self.actions: list[str] = []
        self.observation_text = ""

    def open_url(self, url: str) -> None:
        self.current_url = url
        self.actions.append(f"open_url:{url}")

    def observe(self) -> Observation:
        screenshot_path = self.evidence_dir / "dry-run-screenshot.txt"
        screenshot_path.write_text("dry run screenshot placeholder", encoding="utf-8")
        self.actions.append("observe")
        return Observation(
            screenshot_path=screenshot_path,
            screen_text=self.observation_text,
            current_url=self.current_url,
        )

    def click(self, x: int, y: int) -> None:
        self.actions.append(f"click:{x},{y}")

    def type_text(self, text: str) -> None:
        self.actions.append(f"type_text:{text}")

    def hotkey(self, keys: tuple[str, ...]) -> None:
        self.actions.append(f"hotkey:{'+'.join(keys)}")

    def scroll(self, amount: int) -> None:
        self.actions.append(f"scroll:{amount}")

    def wait(self, seconds: float) -> None:
        self.actions.append(f"wait:{seconds}")

    def upload_file(self, path: Path) -> None:
        self.actions.append(f"upload_file:{path}")

    def notify_human(self, message: str) -> None:
        self.actions.append(f"notify_human:{message}")
