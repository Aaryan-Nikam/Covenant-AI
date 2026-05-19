"""
Ironpass — Anthropic content extractor.

Handles the Anthropic Messages API format:
    POST /anthropic/v1/messages

Anthropic request body:
{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "system": "You are a helpful assistant",   ← top-level string
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {
            "role": "user",
            "content": [                        ← array form (tool results, vision)
                {"type": "text", "text": "Here is my SSN: 123-45-6789"},
                {"type": "image", "source": {...}}
            ]
        }
    ]
}

Key differences from OpenAI:
    - "system" is a top-level field, not a message with role="system"
    - Vision uses {"type": "image", "source": {...}} not "image_url"
    - Tool results have a different structure
"""

import copy

from engine.proxy.extractors.base import BaseContentExtractor, TextSegment

_SEPARATOR = "\n---\n"
# Special index used to track the top-level system prompt
_SYSTEM_MSG_INDEX = -1


class AnthropicContentExtractor(BaseContentExtractor):
    """
    Extracts text from Anthropic Messages API request bodies.
    Handles both string and array message content.
    Extracts the top-level system prompt as well.
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def extract(self, body: dict) -> tuple[str, list[TextSegment]]:
        segments: list[TextSegment] = []
        text_parts: list[str] = []

        # Extract top-level system prompt (Anthropic-specific)
        system = body.get("system", "")
        if system and isinstance(system, str):
            segments.append(TextSegment(
                message_index=_SYSTEM_MSG_INDEX,
                content_index=None,
                original_text=system,
                sanitized_text=None,
            ))
            text_parts.append(system)

        # Extract message content
        for msg_idx, message in enumerate(body.get("messages", [])):
            content = message.get("content", "")

            if isinstance(content, str):
                segments.append(TextSegment(
                    message_index=msg_idx,
                    content_index=None,
                    original_text=content,
                    sanitized_text=None,
                ))
                text_parts.append(content)

            elif isinstance(content, list):
                for content_idx, item in enumerate(content):
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        segments.append(TextSegment(
                            message_index=msg_idx,
                            content_index=content_idx,
                            original_text=text,
                            sanitized_text=None,
                        ))
                        text_parts.append(text)
                    # image, tool_result, tool_use pass through unchanged

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

        # Restore system prompt
        key = (_SYSTEM_MSG_INDEX, None)
        if key in segment_map:
            rebuilt["system"] = segment_map[key]

        # Restore message content
        for msg_idx, message in enumerate(rebuilt.get("messages", [])):
            content = message.get("content", "")

            if isinstance(content, str):
                k = (msg_idx, None)
                if k in segment_map:
                    message["content"] = segment_map[k]

            elif isinstance(content, list):
                for content_idx, item in enumerate(content):
                    if item.get("type") == "text":
                        k = (msg_idx, content_idx)
                        if k in segment_map:
                            item["text"] = segment_map[k]

        return rebuilt
