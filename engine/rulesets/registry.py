"""
Ironpass — Runtime ruleset registry.

In-memory registry of all active rulesets. Loaded at startup from YAML.
Supports per-tenant activation/deactivation without restart.
"""

import logging
from threading import Lock

from engine.detection.models import ActionConfig, Ruleset
from engine.exceptions import RulesetNotFoundError
from engine.config import get_settings

logger = logging.getLogger("ironpass.rulesets.registry")


class RulesetRegistry:
    """
    Runtime registry of loaded rulesets.

    Thread-safe. Supports:
    - Looking up rulesets by ID
    - Activating / deactivating per tenant
    - Merging configs from multiple active rulesets
    - Conflict resolution: highest severity action wins
    """

    # Action priority — higher number = higher severity
    ACTION_PRIORITY = {
        "mask": 1,
        "pseudonymize": 2,
        "tokenize": 3,
        "block": 4,
    }

    def __init__(self):
        self._rulesets: dict[str, Ruleset] = {}
        self._lock = Lock()

    def register(self, ruleset: Ruleset) -> None:
        """Register a validated ruleset."""
        with self._lock:
            self._rulesets[ruleset.ruleset_id] = ruleset
            logger.info(f"Registered ruleset: {ruleset.ruleset_id}")

    def register_all(self, rulesets: dict[str, Ruleset]) -> None:
        """Register multiple rulesets at once."""
        with self._lock:
            self._rulesets.update(rulesets)
            logger.info(f"Registered {len(rulesets)} rulesets")

    def get(self, ruleset_id: str) -> Ruleset:
        """Get a ruleset by ID. Raises RulesetNotFoundError if not found."""
        ruleset = self._rulesets.get(ruleset_id)
        if ruleset is None:
            raise RulesetNotFoundError(ruleset_id)
        return ruleset

    def get_multiple(self, ruleset_ids: list[str]) -> list[Ruleset]:
        """Get multiple rulesets. Raises RulesetNotFoundError for any missing."""
        rulesets = []
        for rid in ruleset_ids:
            rulesets.append(self.get(rid))
        return rulesets

    def list_all(self) -> list[Ruleset]:
        """Return all registered rulesets."""
        return list(self._rulesets.values())

    def list_ids(self) -> list[str]:
        """Return all registered ruleset IDs."""
        return list(self._rulesets.keys())

    def is_registered(self, ruleset_id: str) -> bool:
        """Check if a ruleset is registered."""
        return ruleset_id in self._rulesets

    def get_merged_actions(
        self, ruleset_ids: list[str]
    ) -> dict[str, ActionConfig]:
        """
        Merge action configs from multiple rulesets.
        When the same data_type appears in multiple rulesets,
        the highest severity action wins.

        Action priority: BLOCK > TOKENIZE > PSEUDONYMIZE > MASK
        """
        merged: dict[str, ActionConfig] = {}
        origin_rulesets: dict[str, str] = {}  # data_type -> ruleset_id

        priority_list = get_settings().ruleset_priority

        def get_rs_rank(rid: str) -> int:
            try:
                return len(priority_list) - priority_list.index(rid)
            except ValueError:
                return 0

        for ruleset in self.get_multiple(ruleset_ids):
            new_rs_rank = get_rs_rank(ruleset.ruleset_id)
            for data_type, action in ruleset.actions.items():
                if data_type not in merged:
                    merged[data_type] = action
                    origin_rulesets[data_type] = ruleset.ruleset_id
                else:
                    existing_rs_id = origin_rulesets[data_type]
                    existing_rs_rank = get_rs_rank(existing_rs_id)

                    # 1. Ruleset priority wins
                    if new_rs_rank > existing_rs_rank:
                        merged[data_type] = action
                        origin_rulesets[data_type] = ruleset.ruleset_id
                    elif new_rs_rank < existing_rs_rank:
                        pass  # Keep existing action
                    else:
                        # 2. Tie -> Higher severity action wins
                        existing_priority = self.ACTION_PRIORITY.get(
                            merged[data_type].primary, 0
                        )
                        new_priority = self.ACTION_PRIORITY.get(action.primary, 0)
                        if new_priority > existing_priority:
                            merged[data_type] = action
                            origin_rulesets[data_type] = ruleset.ruleset_id

        return merged

    def unregister(self, ruleset_id: str) -> None:
        """Remove a ruleset from the registry."""
        with self._lock:
            if ruleset_id in self._rulesets:
                del self._rulesets[ruleset_id]
                logger.info(f"Unregistered ruleset: {ruleset_id}")
