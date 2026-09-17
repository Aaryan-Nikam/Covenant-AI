from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from azmeth_agent.mcp_client import McpToolClient
from azmeth_agent.tools import Observation


@dataclass(frozen=True)
class CoastyToolNames:
    screenshot: str = "coasty_take_machine_screenshot"
    execute: str = "coasty_execute_machine_action"


@dataclass(frozen=True)
class CoastyActionCommands:
    navigate: str = "browser_navigate"
    click: str = "click"
    type_text: str = "type"
    hotkey: str = "key_combo"
    scroll: str = "scroll"
    wait: str = "wait"
    upload_file: str = "file_upload"


class CoastyDesktopTools:
    """DesktopTools adapter for Open Computer Use / Coasty MCP.

    Coasty exposes a screenshot tool and an action-dispatcher tool. This adapter
    maps our narrow, safety-checked action schema into those MCP calls.
    """

    def __init__(
        self,
        client: McpToolClient,
        machine_id: str,
        evidence_dir: Path,
        tool_names: CoastyToolNames | None = None,
        action_commands: CoastyActionCommands | None = None,
    ) -> None:
        if not machine_id:
            raise ValueError("machine_id is required for CoastyDesktopTools.")
        self.client = client
        self.machine_id = machine_id
        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.tool_names = tool_names or CoastyToolNames()
        self.action_commands = action_commands or CoastyActionCommands()
        self.current_url: str | None = None

    def open_url(self, url: str) -> None:
        self.current_url = url
        self._execute(self.action_commands.navigate, {"url": url})

    def observe(self) -> Observation:
        result = self.client.call_tool(self.tool_names.screenshot, {"machine_id": self.machine_id})
        screenshot_path = self._write_screenshot(result)
        return Observation(
            screenshot_path=screenshot_path,
            screen_text=str(result.get("text") or result.get("screen_text") or ""),
            current_url=str(result.get("url") or self.current_url) if result.get("url") or self.current_url else None,
        )

    def click(self, x: int, y: int) -> None:
        self._execute(self.action_commands.click, {"x": x, "y": y})

    def type_text(self, text: str) -> None:
        self._execute(self.action_commands.type_text, {"text": text})

    def hotkey(self, keys: tuple[str, ...]) -> None:
        self._execute(self.action_commands.hotkey, {"keys": list(keys)})

    def scroll(self, amount: int) -> None:
        self._execute(self.action_commands.scroll, {"amount": amount})

    def wait(self, seconds: float) -> None:
        self._execute(self.action_commands.wait, {"seconds": seconds})

    def upload_file(self, path: Path) -> None:
        self._execute(self.action_commands.upload_file, {"path": str(path.expanduser().resolve())})

    def notify_human(self, message: str) -> None:
        # Keep notification outside Coasty by default so alerts still work if the
        # MCP server is the failing component.
        print(f"[Azmeth Agent] Human attention required: {message}")

    def _execute(self, command: str, parameters: dict[str, Any]) -> None:
        self.client.call_tool(
            self.tool_names.execute,
            {
                "machine_id": self.machine_id,
                "command": command,
                "parameters": parameters,
            },
        )

    def _write_screenshot(self, result: dict[str, Any]) -> Path:
        path = self.evidence_dir / f"{self._timestamp()}-coasty-screenshot"
        if image_path := result.get("path"):
            source = Path(str(image_path)).expanduser()
            if source.exists():
                target = path.with_suffix(source.suffix or ".png")
                target.write_bytes(source.read_bytes())
                return target
        if image_base64 := result.get("image_base64") or result.get("screenshot_base64"):
            target = path.with_suffix(".png")
            target.write_bytes(base64.b64decode(str(image_base64)))
            return target
        target = path.with_suffix(".json")
        target.write_text(str(result), encoding="utf-8")
        return target

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
