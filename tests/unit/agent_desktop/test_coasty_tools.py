from __future__ import annotations

import base64
from pathlib import Path

from azmeth_agent.coasty_tools import CoastyDesktopTools
from azmeth_agent.mcp_client import FakeMcpClient


def test_coasty_open_url_maps_to_execute_action(tmp_path: Path) -> None:
    client = FakeMcpClient()
    tools = CoastyDesktopTools(client, machine_id="mch_test", evidence_dir=tmp_path)

    tools.open_url("https://app.dripify.io/")

    assert client.calls == [
        (
            "coasty_execute_machine_action",
            {
                "machine_id": "mch_test",
                "command": "browser_navigate",
                "parameters": {"url": "https://app.dripify.io/"},
            },
        )
    ]


def test_coasty_observe_writes_base64_screenshot(tmp_path: Path) -> None:
    png_bytes = b"fake-png"
    client = FakeMcpClient(
        {
            "coasty_take_machine_screenshot": {
                "screenshot_base64": base64.b64encode(png_bytes).decode("ascii"),
                "screen_text": "Import leads",
                "url": "https://app.dripify.io/campaigns",
            }
        }
    )
    tools = CoastyDesktopTools(client, machine_id="mch_test", evidence_dir=tmp_path)

    observation = tools.observe()

    assert observation.screenshot_path.read_bytes() == png_bytes
    assert observation.screen_text == "Import leads"
    assert observation.current_url == "https://app.dripify.io/campaigns"


def test_coasty_upload_file_uses_configured_dispatcher(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text("name,email\n", encoding="utf-8")
    client = FakeMcpClient()
    tools = CoastyDesktopTools(client, machine_id="mch_test", evidence_dir=tmp_path)

    tools.upload_file(csv_path)

    assert client.calls[0][0] == "coasty_execute_machine_action"
    assert client.calls[0][1]["command"] == "file_upload"
    assert client.calls[0][1]["parameters"]["path"] == str(csv_path.resolve())
