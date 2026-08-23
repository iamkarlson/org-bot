"""
Stateless callback_data encoding for search buttons.

All interaction state lives in the button payload (Telegram limit:
64 bytes of UTF-8). Nothing survives-or-breaks on cold starts. Queries
that don't fit the budget get no buttons — the caller degrades to
text-only results, never silent truncation.

Format:
    v1|p|<page>|<query>            page through results
    v1|o|<rank>|<chunk>|<query>    open hit <rank>, content chunk <chunk>
    v1|f|<chunk>|<path>            open note by path (inline-mode /open flow)
"""

from dataclasses import dataclass
from typing import Optional

MAX_CALLBACK_BYTES = 64

OP_PAGE = "p"
OP_OPEN = "o"
OP_FILE = "f"


@dataclass
class CallbackData:
    op: str
    query: str = ""
    page: int = 0
    rank: int = 0
    chunk: int = 0
    path: str = ""


def encode_page(page: int, query: str) -> Optional[str]:
    return _fit(f"v1|{OP_PAGE}|{page}|{query}")


def encode_open(rank: int, chunk: int, query: str) -> Optional[str]:
    return _fit(f"v1|{OP_OPEN}|{rank}|{chunk}|{query}")


def encode_file(chunk: int, path: str) -> Optional[str]:
    return _fit(f"v1|{OP_FILE}|{chunk}|{path}")


def decode(data: str) -> Optional[CallbackData]:
    """Parse callback data; None for anything unrecognized."""
    if not data or not data.startswith("v1|"):
        return None
    try:
        _, op, rest = data.split("|", 2)
        if op == OP_PAGE:
            page_str, query = rest.split("|", 1)
            return CallbackData(op=op, query=query, page=int(page_str))
        if op == OP_OPEN:
            rank_str, chunk_str, query = rest.split("|", 2)
            return CallbackData(
                op=op, query=query, rank=int(rank_str), chunk=int(chunk_str)
            )
        if op == OP_FILE:
            chunk_str, path = rest.split("|", 1)
            return CallbackData(op=op, path=path, chunk=int(chunk_str))
    except ValueError:
        return None
    return None


def _fit(data: str) -> Optional[str]:
    if len(data.encode("utf-8")) > MAX_CALLBACK_BYTES:
        return None
    return data
