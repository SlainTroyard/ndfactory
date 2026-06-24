"""Text normalization utilities for cleaning vulnerability descriptions"""
import re
import logging

logger = logging.getLogger(__name__)

# HTML tag pattern
HTML_TAG_RE = re.compile(r"<[^>]+>")
# Multiple whitespace pattern
MULTI_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text by stripping HTML tags and collapsing whitespace.

    Steps:
        1. Strip HTML tags.
        2. Collapse multiple whitespace characters into a single space.
        3. Strip leading/trailing whitespace.

    Args:
        text: Raw input text (may contain HTML, extra whitespace).

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    # Strip HTML tags
    text = HTML_TAG_RE.sub("", text)

    # Collapse whitespace
    text = MULTI_WS_RE.sub(" ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text
