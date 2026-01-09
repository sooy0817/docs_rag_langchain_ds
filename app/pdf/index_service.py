# app/pdf/index_service.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from elasticsearch.helpers import bulk

from app.core.config import settings
from app.core.es import get_es
from app.core.embeddings import embed_texts
from app.pdf.chunker import Chunk


def make_chunk_doc_id(pdf_id: str, chunk_id: int) -> str:
    return f"{pdf_id}:{chunk_id}"


def index_pdf_chunks(
    pdf_id: str,
    pdf_path: str,
    chunks: List[Chunk],
    *,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Chunk(page_no 포함) 리스트를 임베딩하여 Elasticsearch에 bulk index.
    return: indexed document count
    """
    if not chunks:
        return 0

    es = get_es()

    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)

    meta = extra_meta or {}

    actions = []
    for c, vec in zip(chunks, vectors):
        actions.append(
            {
                "_op_type": "index",
                "_index": settings.PDF_INDEX,
                "_id": make_chunk_doc_id(pdf_id, c.chunk_id),
                "_source": {
                    "pdf_id": pdf_id,
                    "pdf_path": pdf_path,
                    "page_no": c.page_no,
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "vector": vec,
                    **meta,
                },
            }
        )

    success, _ = bulk(es, actions, refresh=True)
    return success
