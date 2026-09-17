from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class McpToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class McpServerCommand:
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    cwd: Path | None = None


class StdioMcpClient:
    """Minimal synchronous MCP stdio client for tool calls.

    This keeps our product independent from any specific MCP host. It can launch
    servers such as `npx -y @coasty/mcp` and call standard MCP tools through
    JSON-RPC. The implementation is deliberately small so it can be audited.
    """

    def __init__(self, server: McpServerCommand, timeout_seconds: float = 60) -> None:
        self.server = server
        self.timeout_seconds = timeout_seconds
        self._next_id = 1
        self._lock = threading.Lock()
        self._process = subprocess.Popen(
            [server.command, *server.args],
            cwd=server.cwd,
            env=server.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "azmeth-agent", "version": "0.1.0"}})
        self._notify("notifications/initialized", {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            return self._read_response(request_id)

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise RuntimeError("MCP server stdin is closed.")
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()

    def _read_response(self, request_id: int) -> dict[str, Any]:
        if self._process.stdout is None:
            raise RuntimeError("MCP server stdout is closed.")
        while True:
            line = self._process.stdout.readline()
            if not line:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                raise RuntimeError(f"MCP server closed before response. stderr={stderr[-1000:]}")
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"MCP error: {message['error']}")
            return message.get("result") or {}


class FakeMcpClient:
    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self.responses.get(name, {"success": True})

    def close(self) -> None:
        return None
