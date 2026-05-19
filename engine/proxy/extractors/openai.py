"""
Ironpass — OpenAI content extractor.

Handles the OpenAI chat completions format:
    messages: [{"role": "user", "content": "..."}]

Also handles vision/tool API (array content):
    messages: [{"role": "user", "content": [{"type": "text", "text": "..."}]}]
"""

import copy

from engine.proxy.extractors.base import BaseContentExtractor, TextSegment

_SEPARATOR = "\n---\n"


class OpenAIContentExtractor(BaseContentExtractor):
    """
    Extracts text from OpenAI chat completions request bodies.
    Preserves vision API passthrough (image_url blocks untouched).
    """

    @property
    def provider_name(self) -> str:
        return "openai"

    def extract(self, body: dict) -> tuple[str, list[TextSegment]]:
        messages = body.get("messages", [])
        segments: list[TextSegment] = []
        text_parts: list[str] = []

        for msg_idx, message in enumerate(messages):
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
                    # image_url and other types pass through unchanged

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
                else segment.original_text  # fallback: keep original
            )

        segment_map = {
            (s.message_index, s.content_index): s.sanitized_text
            for s in segments
        }

        rebuilt = copy.deepcopy(body)
        for msg_idx, message in enumerate(rebuilt.get("messages", [])):
            content = message.get("content", "")

            if isinstance(content, str):
                key = (msg_idx, None)
                if key in segment_map:
                    message["content"] = segment_map[key]

            elif isinstance(content, list):
                for content_idx, item in enumerate(content):
                    if item.get("type") == "text":
                        key = (msg_idx, content_idx)
                        if key in segment_map:
                            item["text"] = segment_map[key]

        return rebuilt
