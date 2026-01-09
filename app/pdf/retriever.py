# app/pdf/retriever.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.es import get_es
from app.core.config import settings
from app.core.embeddings import embed_texts


def search_pdf_chunks(
    query: str,
    *,
    top_k: int = 10,
    pdf_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Elasticsearch(pdf_chunks_v1)에서 KNN 기반으로 chunk 검색.
    반환: 각 chunk의 _source dict 리스트
    """
    es = get_es()

    # query -> vector
    qvec = embed_texts([query])[0]

    # optional filter
    filters = []
    if pdf_id:
        filters.append({"term": {"pdf_id": pdf_id}})

    body: Dict[str, Any] = {
        "size": top_k,
        "_source": [
            "pdf_id", "pdf_path", "page_no", "chunk_id",
            "text",
            "chunk_strategy", "chunk_profile", "chunk_profile_reason",
            "chunk_size", "chunk_overlap",
        ],
        "knn": {
            "field": "vector",
            "query_vector": qvec,
            "k": top_k,
            "num_candidates": max(100, top_k * 20),
        },
    }

    if filters:
        body["knn"]["filter"] = filters

    resp = es.search(index=settings.PDF_INDEX, body=body)
    hits = resp.get("hits", {}).get("hits", [])
    return [h.get("_source", {}) for h in hits]
