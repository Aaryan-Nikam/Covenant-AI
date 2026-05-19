"""
Ironpass — Google Gemini content extractor.

Handles the Google Generative Language API format:
    POST /google/v1/models/{model}:generateContent

Google request body:
{
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": "What is the capital of France?"},
                {"inlineData": {"mimeType": "image/jpeg", "data": "..."}}
            ]
        },
        {
            "role": "model",
            "parts": [{"text": "Paris."}]
        }
    ],
    "systemInstruction": {            ← optional top-level system prompt
        "parts": [{"text": "You are a helpful assistant."}]
    }
}

Key differences from OpenAI:
    - "contents" not "messages"
    - "parts" not "content"
    - "role": "model" not "assistant"
    - "systemInstruction" is a top-level object with its own "parts" array
"""

import copy

from engine.proxy.extractors.base import BaseContentExtractor, TextSegment

_SEPARATOR = "\n---\n"
_SYSTEM_PART_INDEX = -1


class GoogleContentExtractor(BaseContentExtractor):
    """
    Extracts text from Google Generative Language API request bodies.
    Handles the 'contents[].parts[].text' structure.
    """

    @property
    def provider_name(self) -> str:
        return "google"

    def extract(self, body: dict) -> tuple[str, list[TextSegment]]:
        segments: list[TextSegment] = []
        text_parts: list[str] = []

        # System instruction (optional top-level)
        system_instruction = body.get("systemInstruction", {})
        for part_idx, part in enumerate(system_instruction.get("parts", [])):
            if "text" in part:
                segments.append(TextSegment(
                    message_index=_SYSTEM_PART_INDEX,
                    content_index=part_idx,
                    original_text=part["text"],
                    sanitized_text=None,
                ))
                text_parts.append(part["text"])

        # Message contents
        for msg_idx, content in enumerate(body.get("contents", [])):
            for part_idx, part in enumerate(content.get("parts", [])):
                if "text" in part:
                    segments.append(TextSegment(
                        message_index=msg_idx,
                        content_index=part_idx,
                        original_text=part["text"],
                        sanitized_text=None,
                    ))
                    text_parts.append(part["text"])
                # inlineData, fileData, functionCall/Response pass through

        combined = _SEPARATOR.join(text_parts)
        return combined, segments

    def rebuild(
        self,
        body: dict,
        segments: list[TextSegment],
        sanitized_combined: str,
    ) -> dict:
        sanitized_parts = sanitized_combined.split(_SEPARATOR)

        for i, segment in enumerate(segments):
            segment.sanitized_text = (
                sanitized_parts[i] if i < len(sanitized_parts)
                else segment.original_text
            )

        segment_map = {
            (s.message_index, s.content_index): s.sanitized_text
            for s in segments
        }

        rebuilt = copy.deepcopy(body)

        # Restore system instruction
        for part_idx, part in enumerate(
            rebuilt.get("systemInstruction", {}).get("parts", [])
        ):
            if "text" in part:
                k = (_SYSTEM_PART_INDEX, part_idx)
                if k in segment_map:
                    part["text"] = segment_map[k]

        # Restore message contents
        for msg_idx, content in enumerate(rebuilt.get("contents", [])):
            for part_idx, part in enumerate(content.get("parts", [])):
                if "text" in part:
                    k = (msg_idx, part_idx)
                    if k in segment_map:
                        part["text"] = segment_map[k]

        return rebuilt
