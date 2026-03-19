import pytest
from engine.proxy.content_extractor import ContentExtractor, TextSegment

def test_extract_string_content():
    extractor = ContentExtractor()
    messages = [
        {"role": "system", "content": "system msg"},
        {"role": "user", "content": "user msg"}
    ]
    combined, segments = extractor.extract(messages)
    
    assert combined == "system msg\n---\nuser msg"
    assert len(segments) == 2
    assert segments[0].original_text == "system msg"
    assert segments[1].original_text == "user msg"

def test_extract_array_content():
    extractor = ContentExtractor()
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": "http://example.com"}
        ]}
    ]
    combined, segments = extractor.extract(messages)
    
    assert combined == "hello"
    assert len(segments) == 1
    assert segments[0].original_text == "hello"
    assert segments[0].content_index == 0

def test_rebuild_identical_structure():
    extractor = ContentExtractor()
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": "http://example.com"}
        ]}
    ]
    combined, segments = extractor.extract(messages)
    
    rebuilt = extractor.rebuild(messages, segments, combined)
    assert rebuilt == messages

def test_rebuild_sanitized_content():
    extractor = ContentExtractor()
    messages = [
        {"role": "user", "content": "My card is 4111"},
        {"role": "assistant", "content": "OK"}
    ]
    combined, segments = extractor.extract(messages)
    
    sanitized_combined = "My card is [CARD]\n---\nOK"
    rebuilt = extractor.rebuild(messages, segments, sanitized_combined)
    
    assert rebuilt[0]["content"] == "My card is [CARD]"
    assert rebuilt[1]["content"] == "OK"
