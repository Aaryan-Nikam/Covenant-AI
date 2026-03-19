"""
Extracts text content from OpenAI message format for scanning.
Rebuilds sanitized messages array after scanning.

OpenAI messages format:
[
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Charge card 4111111111111111"},
    {"role": "assistant", "content": "I'll process that payment"}
]

Content can also be an array (vision API):
[
    {"role": "user", "content": [
        {"type": "text", "text": "Here is my card: 4111111111111111"},
        {"type": "image_url", "image_url": {"url": "..."}}
    ]}
]

Rules:
- Extract ALL text content from ALL messages
- Preserve role and position information for rebuilding
- Handle both string content and array content
- Never modify image_url content
- Track position of each extracted text segment for rebuilding
"""

from dataclasses import dataclass


@dataclass
class TextSegment:
    """A piece of text extracted from the messages array"""
    message_index: int          # Which message this came from
    content_index: int | None   # If content is array, which item
    original_text: str          # The raw text before scanning
    sanitized_text: str | None  # Set after scanning, None until then


class ContentExtractor:

    def extract(self, messages: list[dict]) -> tuple[str, list[TextSegment]]:
        """
        Extracts all text from messages array.

        Returns:
            combined_content: str
                Single string of all text concatenated with newlines.
                This is what gets passed to the DetectionEngine.

            segments: list[TextSegment]
                Ordered list of where each piece of text came from.
                Used by rebuild() to put sanitized text back in the right place.
        """
        segments = []
        text_parts = []

        for msg_idx, message in enumerate(messages):
            content = message.get("content", "")

            if isinstance(content, str):
                # Simple string content
                segment = TextSegment(
                    message_index=msg_idx,
                    content_index=None,
                    original_text=content,
                    sanitized_text=None
                )
                segments.append(segment)
                text_parts.append(content)

            elif isinstance(content, list):
                # Array content (vision API, tool results, etc.)
                for content_idx, content_item in enumerate(content):
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        segment = TextSegment(
                            message_index=msg_idx,
                            content_index=content_idx,
                            original_text=text,
                            sanitized_text=None
                        )
                        segments.append(segment)
                        text_parts.append(text)
                    # Skip image_url and other non-text types
                    # They are passed through unchanged

        combined = "\n---\n".join(text_parts)
        return combined, segments

    def rebuild(
        self,
        messages: list[dict],
        segments: list[TextSegment],
        sanitized_combined: str,
    ) -> list[dict]:
        """
        Rebuilds the messages array with sanitized content.

        Takes the sanitized combined string, splits it back by the
        separator used in extract(), and maps each piece back to
        the correct message and content position.

        Returns a new messages array — never mutates the original.
        """
        # Split sanitized content back into segments
        sanitized_parts = sanitized_combined.split("\n---\n")

        # Map sanitized text back to segments
        for i, segment in enumerate(segments):
            if i < len(sanitized_parts):
                segment.sanitized_text = sanitized_parts[i]
            else:
                # Fallback: keep original if mapping fails
                segment.sanitized_text = segment.original_text

        # Build segment lookup: (message_index, content_index) -> sanitized_text
        segment_map = {
            (s.message_index, s.content_index): s.sanitized_text
            for s in segments
        }

        # Rebuild messages array
        import copy
        rebuilt = copy.deepcopy(messages)

        for msg_idx, message in enumerate(rebuilt):
            content = message.get("content", "")

            if isinstance(content, str):
                key = (msg_idx, None)
                if key in segment_map:
                    message["content"] = segment_map[key]

            elif isinstance(content, list):
                for content_idx, content_item in enumerate(content):
                    if content_item.get("type") == "text":
                        key = (msg_idx, content_idx)
                        if key in segment_map:
                            content_item["text"] = segment_map[key]

        return rebuilt
