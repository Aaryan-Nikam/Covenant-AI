"""
Ironpass — Base content extractor interface.

Every LLM provider has a different request format.
This base class defines the contract all extractors must implement.

Implementations:
    OpenAIContentExtractor   — /openai/* routes (GPT-4, GPT-4o, etc.)
    AnthropicContentExtractor — /anthropic/* routes (Claude)
    GoogleContentExtractor   — /google/* routes (Gemini)

The compliance pipeline (detect → act → forward → log) is identical
for all providers. Only extraction and forwarding differ.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TextSegment:
    """A piece of text extracted from a provider request body."""
    message_index: int           # Which message / turn this came from
    content_index: int | None    # Sub-index if content is an array
    original_text: str           # Raw text before scanning
    sanitized_text: str | None   # Set after scanning, None until then


class BaseContentExtractor(ABC):
    """
    Abstract base for provider-specific content extractors.

    Implementors must handle:
        extract()  — pull all user-visible text out of the request body
        rebuild()  — put sanitized text back into the original structure

    The combined string from extract() is what gets scanned.
    The rebuilt dict from rebuild() is what gets forwarded to the LLM.
    """

    @abstractmethod
    def extract(self, body: dict) -> tuple[str, list[TextSegment]]:
        """
        Extract all scannable text from the provider request body.

        Returns:
            combined_content: str
                All text joined by '\\n---\\n'. Passed to DetectionEngine.
            segments: list[TextSegment]
                Positional mapping used by rebuild() to restore sanitized text.
        """
        ...

    @abstractmethod
    def rebuild(
        self,
        body: dict,
        segments: list[TextSegment],
        sanitized_combined: str,
    ) -> dict:
        """
        Rebuild the provider request body with sanitized content.

        Returns a new dict — never mutates the original.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...
