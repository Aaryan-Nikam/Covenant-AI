from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from azmeth_agent.vision_brain import VisionModelClient


class JsonPost(Protocol):
    def __call__(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60
    temperature: float = 0

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


class OpenAICompatibleVisionClient(VisionModelClient):
    """Vision model client for OpenAI-compatible chat-completions endpoints."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        post_json: JsonPost | None = None,
    ) -> None:
        if not config.base_url:
            raise ValueError("base_url is required.")
        if not config.api_key:
            raise ValueError("api_key is required.")
        if not config.model:
            raise ValueError("model is required.")
        self.config = config
        self.post_json = post_json or post_json_urllib

    def decide(self, prompt: str, screenshot_path: Path) -> str:
        image_url = encode_image_data_url(screenshot_path)
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a cautious computer-use agent. Return exactly one JSON object "
                        "matching the user's schema. Do not include markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        }
        response = self.post_json(
            self.config.chat_completions_url,
            payload,
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            self.config.timeout_seconds,
        )
        return extract_chat_message(response)


def encode_image_data_url(path: Path) -> str:
    data = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_chat_message(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Vision model response did not include choices.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            item.get("text")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if text_parts:
            return "\n".join(text_parts)
    raise RuntimeError("Vision model response did not include text content.")


def post_json_urllib(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Vision model request failed with HTTP {exc.code}: {detail}") from exc
