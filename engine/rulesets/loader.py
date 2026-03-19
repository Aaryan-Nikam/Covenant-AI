"""
Ironpass — Ruleset YAML loader.

Loads all YAML rulesets from the definitions directory at startup.
Any ruleset that fails validation is rejected with a warning, not a crash.

Critical Rule #9: Adding a new ruleset means adding a YAML file.
No Python code changes required.
"""

import logging
from pathlib import Path

import yaml

from engine.detection.models import Ruleset
from engine.exceptions import RulesetValidationError
from engine.rulesets.validator import RulesetValidator

logger = logging.getLogger("ironpass.rulesets.loader")


class RulesetLoader:
    """
    Loads and validates YAML rulesets at startup.
    Any ruleset that fails validation is rejected with clear error message.
    Valid rulesets are returned for registration.
    """

    DEFINITIONS_PATH = Path(__file__).parent / "definitions"

    def __init__(self):
        self.validator = RulesetValidator()

    def load_all(self) -> dict[str, Ruleset]:
        """
        Loads all YAML files from definitions directory.
        Returns dict of {ruleset_id: Ruleset}.
        Logs warning for any failed rulesets, continues loading others.
        """
        rulesets: dict[str, Ruleset] = {}

        if not self.DEFINITIONS_PATH.exists():
            logger.warning(
                f"Definitions directory not found: {self.DEFINITIONS_PATH}"
            )
            return rulesets

        yaml_files = list(self.DEFINITIONS_PATH.glob("*.yaml")) + list(
            self.DEFINITIONS_PATH.glob("*.yml")
        )

        if not yaml_files:
            logger.warning(
                f"No YAML files found in {self.DEFINITIONS_PATH}"
            )
            return rulesets

        for filepath in sorted(yaml_files):
            try:
                ruleset = self.load_from_file(str(filepath))
                rulesets[ruleset.ruleset_id] = ruleset
                logger.info(
                    f"Loaded ruleset: {ruleset.ruleset_id} "
                    f"({ruleset.name}, {len(ruleset.detectors)} detectors)"
                )
            except RulesetValidationError as e:
                logger.warning(f"Skipping invalid ruleset {filepath.name}: {e}")
            except yaml.YAMLError as e:
                logger.warning(f"Skipping malformed YAML {filepath.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading {filepath.name}: {e}")

        logger.info(f"Loaded {len(rulesets)} rulesets total")
        return rulesets

    def load_from_file(self, filepath: str) -> Ruleset:
        """Load and validate a single YAML ruleset file."""
        with open(filepath, "r") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise RulesetValidationError(
                ruleset_id="<unknown>",
                field="root",
                reason="YAML root must be a mapping/dict",
            )

        return self.validator.validate(raw)
