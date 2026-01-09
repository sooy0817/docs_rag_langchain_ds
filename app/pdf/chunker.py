# app/pdf/chunker.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    page_no: int
    chunk_id: int
    text: str


def chunk_pages(
    pages: List[tuple[int, str]],
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> List[Chunk]:
    """
    pages: [(page_no, page_text), ...]
    페이지별로 쪼갠 뒤, chunk_id는 전체에서 증가하도록 부여
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    chunks: List[Chunk] = []
    global_chunk_id = 0

    for page_no, text in pages:
        text = (text or "").strip()
        if not text:
            continue

        parts = splitter.split_text(text)
        for part in parts:
            part = part.strip()
            if not part:
                continue

            chunks.append(
                Chunk(
                    page_no=page_no,
                    chunk_id=global_chunk_id,
                    text=part,
                )
            )
            global_chunk_id += 1

    return chunks
