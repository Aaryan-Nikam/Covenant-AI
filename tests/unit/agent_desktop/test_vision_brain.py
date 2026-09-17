from __future__ import annotations

from azmeth_agent.actions import ActionRisk, ActionType
from azmeth_agent.vision_brain import parse_action_json


def test_parse_action_json_accepts_strict_action() -> None:
    action = parse_action_json(
        '{"action_type":"click","reason":"open import","risk":"low","x":10,"y":20}'
    )

    assert action.action_type == ActionType.CLICK
    assert action.risk == ActionRisk.LOW
    assert action.x == 10
    assert action.y == 20


def test_parse_action_json_escalates_invalid_json() -> None:
    action = parse_action_json("not-json")

    assert action.action_type == ActionType.ESCALATE
    assert "invalid JSON" in (action.message or "")
