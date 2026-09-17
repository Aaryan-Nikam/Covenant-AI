from __future__ import annotations

from pathlib import Path
from typing import Any

from azmeth_agent.model_clients import (
    OpenAICompatibleConfig,
    OpenAICompatibleVisionClient,
    encode_image_data_url,
    extract_chat_message,
)


def test_encode_image_data_url(tmp_path: Path) -> None:
    image = tmp_path / "screen.png"
    image.write_bytes(b"abc")

    assert encode_image_data_url(image) == "data:image/png;base64,YWJj"


def test_extract_chat_message_from_string_content() -> None:
    message = extract_chat_message({"choices": [{"message": {"content": '{"action_type":"wait"}'}}]})

    assert message == '{"action_type":"wait"}'


def test_openai_compatible_client_posts_screenshot_payload(tmp_path: Path) -> None:
    image = tmp_path / "screen.png"
    image.write_bytes(b"abc")
    calls: list[tuple[str, dict[str, Any], dict[str, str], float]] = []

    def fake_post(
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        calls.append((url, payload, headers, timeout_seconds))
        return {"choices": [{"message": {"content": '{"action_type":"wait","seconds":1}'}}]}

    client = OpenAICompatibleVisionClient(
        OpenAICompatibleConfig(
            base_url="https://api.example.com/v1",
            api_key="secret",
            model="vision-model",
        ),
        post_json=fake_post,
    )

    result = client.decide("Return JSON", image)

    assert result == '{"action_type":"wait","seconds":1}'
    url, payload, headers, timeout = calls[0]
    assert url == "https://api.example.com/v1/chat/completions"
    assert payload["model"] == "vision-model"
    assert payload["messages"][1]["content"][1]["image_url"]["url"] == "data:image/png;base64,YWJj"
    assert headers["Authorization"] == "Bearer secret"
    assert timeout == 60
