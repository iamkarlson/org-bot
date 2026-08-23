"""
Org subtree extraction and Telegram-sized chunking for search hits.

A hit that matched a body line gets the subtree of the heading containing
that line; a title/preamble match gets the file from the top.
"""

import re
from typing import List, Optional

_HEADING_RE = re.compile(r"^(\*+)\s")

# Telegram's hard limit is 4096; leave headroom for the hit header line.
CHUNK_SIZE = 3500


def extract_subtree(text: str, line_no: Optional[int]) -> str:
    """Return the org subtree containing line_no, or the whole file when
    the match was in the title/preamble (line_no is None or precedes any heading)."""
    lines = text.split("\n")

    if line_no is None or line_no >= len(lines):
        return text

    # Walk up to the nearest heading at or above the matched line.
    heading_line = None
    heading_level = None
    for i in range(line_no, -1, -1):
        match = _HEADING_RE.match(lines[i])
        if match:
            heading_line = i
            heading_level = len(match.group(1))
            break

    if heading_line is None:
        # Match sits in the preamble before any heading.
        return text

    # Subtree ends at the next heading of the same or lower level.
    end = len(lines)
    for i in range(heading_line + 1, len(lines)):
        match = _HEADING_RE.match(lines[i])
        if match and len(match.group(1)) <= heading_level:
            end = i
            break

    return "\n".join(lines[heading_line:end])


def chunk_text(text: str, size: int = CHUNK_SIZE) -> List[str]:
    """Split text into Telegram-sized chunks, preferring line boundaries."""
    if not text:
        return [""]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= size:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    return chunks
