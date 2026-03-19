"""
Ironpass — Layer 2: Luhn card number validation.

Mathematical validation of card number candidates from Layer 1.
Called only on regex hits for credit_card patterns.
Eliminates false positives — if Luhn fails, the detection is dropped.

Luhn algorithm:
1. Starting from rightmost digit, double every second digit
2. If doubled value > 9, subtract 9
3. Sum all digits
4. If total mod 10 == 0: valid card number
"""

import logging

from engine.detection.models import Detection

logger = logging.getLogger("ironpass.detection.luhn")


class LuhnValidator:
    """
    Layer 2: Mathematical validation of card number candidates.
    Only processes detections with data_type == "credit_card".
    """

    def validate(self, candidate: str) -> bool:
        """
        Returns True if candidate passes Luhn check.
        Strip spaces and hyphens before checking.
        """
        # Remove spaces, hyphens, and other non-digit characters
        digits = "".join(c for c in candidate if c.isdigit())

        if len(digits) < 12 or len(digits) > 19:
            return False

        total = 0
        reverse_digits = digits[::-1]

        for i, char in enumerate(reverse_digits):
            digit = int(char)

            # Double every second digit (starting from index 1)
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9

            total += digit

        return total % 10 == 0

    def filter_detections(
        self, detections: list[Detection]
    ) -> list[Detection]:
        """
        Takes card number detections from regex.
        Returns only those that pass Luhn validation.
        Non-credit-card detections pass through unchanged.
        """
        filtered: list[Detection] = []

        for detection in detections:
            print(f"LUHN CHECKING: '{detection.value}' for {detection.data_type}")
            # Only validate credit_card data types
            if detection.data_type != "credit_card":
                filtered.append(detection)
                continue

            if self.validate(detection.value):
                # Luhn passed — boost confidence and mark as layer 2 validated
                validated = detection.model_copy(
                    update={
                        "layer": 2,
                        "confidence": min(detection.confidence + 0.05, 1.0),
                    }
                )
                filtered.append(validated)
                logger.debug(f"Luhn validated: {detection.detector_id}")
            else:
                # Luhn failed — drop this detection (false positive)
                logger.debug(
                    f"Luhn rejected: {detection.detector_id} "
                    f"value ending in ...{detection.value[-4:]}"
                )

        return filtered
