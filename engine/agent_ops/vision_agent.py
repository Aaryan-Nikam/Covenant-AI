from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from engine.agent_ops.schemas import VisualAgentAction, VisualAgentDecisionRequest


SYSTEM_PROMPT = """You are a cautious visual browser agent operating Dripify through screenshots, clicks, typing, scrolling, and waits.
Return exactly one JSON object. No markdown.

Allowed actions:
{"action_type":"click","reason":"...","x":123,"y":456}
{"action_type":"click_target","reason":"...","target_index":0}
{"action_type":"click_text","reason":"...","target_text":"Upload leads"}
{"action_type":"type_text","reason":"...","text":"..."}
{"action_type":"scroll","reason":"...","delta_y":600}
{"action_type":"wait","reason":"...","seconds":1}
{"action_type":"complete","reason":"...","message":"..."}
{"action_type":"escalate","reason":"...","message":"..."}

Goal: use visible Dripify UI to reach the selected campaign's upload/import leads flow and complete the CSV import.
Do not change campaign settings, limits, billing, integrations, sequence copy, or delete anything.
Escalate on login, 2FA, CAPTCHA, billing, permission prompts, unclear campaign choice, or a native file chooser.
If you reach a native file chooser or browser upload dialog, escalate with message "native_file_picker_required".
Coordinates must be absolute pixels in the screenshot.

Observation protocol:
1) Prefer the list of visible clickable targets from the current page.
2) Use the screenshot to confirm page state.
3) Fall back to visible text only when the clickable list does not expose a good target.
4) Return one action only.
"""


def decide_next_action(request: VisualAgentDecisionRequest) -> VisualAgentAction:
    if not os.getenv("VISION_MODEL_API_KEY"):
        return heuristic_decision(request)
    return model_decision(request)


def heuristic_decision(request: VisualAgentDecisionRequest) -> VisualAgentAction:
    # Cheap fallback for local testing. It proves the execution loop moves, but
    # real Dripify navigation should use the configured vision model.
    visible = (request.visible_text or "").lower()
    campaign_name = request.campaign_name or extract_campaign_name(request.instruction)
    campaign_target = campaign_name.lower() if campaign_name else ""
    clickables = request.clickable_targets or []
    if request.step_index == 0:
        best = best_clickable(clickables, [campaign_target, "draft", "new campaign", "campaigns", "campaign"])
        if best is not None:
            return VisualAgentAction(
                action_type="click",
                reason="use the visible clickable target that best matches the current campaign state",
                target_index=best,
            )
        if "draft" in visible:
            return VisualAgentAction(
                action_type="click_text",
                reason="open the visible campaign row from the campaigns list",
                target_text="draft",
            )
        if "new campaign" in visible:
            return VisualAgentAction(
                action_type="click_text",
                reason="open the visible new campaign control if no campaign row is obvious",
                target_text="new campaign",
            )
        return VisualAgentAction(
            action_type="click_text",
            reason="open the most relevant campaign row or control from the visible page",
            target_text=campaign_name or "campaigns|campaign",
        )
    if request.step_index == 1:
        if any(token in visible for token in ("upload leads", "import leads", "add leads")):
            return VisualAgentAction(
                action_type="click_text",
                reason="open the visible upload/import leads control",
                target_text="upload leads",
            )
        return VisualAgentAction(
            action_type="wait",
            reason="wait for campaign navigation to settle",
            seconds=1,
        )
    return VisualAgentAction(
        action_type="escalate",
        reason="vision model not configured",
        message="Set VISION_MODEL_BASE_URL, VISION_MODEL_API_KEY, and VISION_MODEL_NAME to continue autonomously.",
    )


def extract_campaign_name(instruction: str) -> str | None:
    for line in instruction.splitlines():
        if line.lower().startswith("campaign:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def best_clickable(clickables: list[dict[str, object]], needles: list[str]) -> int | None:
    best_index: int | None = None
    best_score = 0
    lowered_needles = [needle.lower() for needle in needles if needle]
    for index, item in enumerate(clickables):
        label = str(item.get("text") or item.get("ariaLabel") or item.get("title") or "").lower()
        if not label:
            continue
        score = 0
        for needle in lowered_needles:
            if not needle:
                continue
            if label == needle:
                score += 120
            elif label.startswith(needle):
                score += 95
            elif needle in label:
                score += 80
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def model_decision(request: VisualAgentDecisionRequest) -> VisualAgentAction:
    base_url = os.getenv("VISION_MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("VISION_MODEL_API_KEY", "")
    model = os.getenv("VISION_MODEL_NAME", "gpt-4.1")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Instruction:\n{request.instruction}\n\n"
                            f"Current URL: {request.current_url}\n"
                            f"Visible text: {request.visible_text}\n"
                            f"Clickable targets: {json.dumps(request.clickable_targets[:25])}\n"
                            f"Step: {request.step_index}\n"
                            f"History: {json.dumps(request.history[-8:])}\n\n"
                            "Choose the next single browser action."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": request.screenshot_data_url}},
                ],
            },
        ],
    }
    response = post_json(
        f"{base_url}/chat/completions",
        payload,
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    content = response["choices"][0]["message"]["content"]
    try:
        raw = json.loads(extract_json_text(content))
        return VisualAgentAction.model_validate(raw)
    except Exception as exc:
        return VisualAgentAction(
            action_type="escalate",
            reason="model returned invalid action JSON",
            message=str(exc),
        )


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Vision request failed with HTTP {exc.code}: {detail}") from exc


def extract_json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found.")
    return stripped[start : end + 1]
