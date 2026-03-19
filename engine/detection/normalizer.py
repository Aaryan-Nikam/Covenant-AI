# engine/detection/normalizer.py
import re
import html
import unicodedata

class ContentNormalizer:
    """
    Strips evasion characters from a COPY of content before scanning.
    Original content is preserved for action application.
    Normalizer output is used ONLY for detection.
    """

    INVISIBLE_UNICODE = re.compile(
        r'[\u200b\u200c\u200d\u200e\u200f'
        r'\u202a-\u202e\u2060-\u2064'
        r'\ufeff\u00ad]'
    )

    def normalize(self, content: str) -> str:
        # Step 1: Decode HTML entities (&shy; &#x34; &amp; etc)
        content = html.unescape(content)
        # Step 2: Strip invisible unicode characters
        content = self.INVISIBLE_UNICODE.sub('', content)
        # Step 3: Normalize unicode to NFC form
        content = unicodedata.normalize('NFC', content)
        return content
