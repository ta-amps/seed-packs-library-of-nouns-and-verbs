"""Standard-library tools for paste deduplication, content-addressed chunking, and situation mining."""

from .miner import (
    DEFAULT_SHINGLE_SIZE,
    chunk_canonical_blocks,
    collapse_duplicate_blocks,
    extract_situations_and_gaps,
    mine_brainstorm_text,
    shingle_jaccard,
    split_repeated_pastes,
)

__all__ = [
    "DEFAULT_SHINGLE_SIZE",
    "chunk_canonical_blocks",
    "collapse_duplicate_blocks",
    "extract_situations_and_gaps",
    "mine_brainstorm_text",
    "shingle_jaccard",
    "split_repeated_pastes",
]
