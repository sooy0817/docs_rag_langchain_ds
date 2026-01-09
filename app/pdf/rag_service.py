# app/pdf/rag_service.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from app.llm.client import get_llm
from app.pdf.retriever import search_pdf_chunks
from app.pdf.url_utils import pdf_url_from_path, viewer_url
from app.pdf.schemas import AskPdfResponse, PdfSource

def _build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"""[CONTEXT {i}]
pdf_id: {c.get('pdf_id')}
page_no: {c.get('page_no')}
chunk_id: {c.get('chunk_id')}
chunk_profile: {c.get('chunk_profile')}
text:
{c.get('text','')}
"""
        )
    return "\n\n".join(parts).strip()

def answer_pdf_question(
    question: str,
    *,
    top_k: int = 10,
    pdf_id: Optional[str] = None,
) -> AskPdfResponse:
    chunks = search_pdf_chunks(question, top_k=top_k, pdf_id=pdf_id)
    context = _build_context(chunks)

    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "너는 사내문서 RAG 어시스턴트다. "
         "주어진 컨텍스트에 근거해서만 답해라. "
         "모르면 모른다고 답해라. "
         "답변 끝에 근거로 사용한 pdf_id와 page_no를 bullet로 적어라."),
        ("user", "질문: {question}\n\n컨텍스트:\n{context}")
    ])

    msg = (prompt | llm).invoke({"question": question, "context": context})

    sources: List[PdfSource] = []
    for c in chunks:
        purl = pdf_url_from_path(c["pdf_path"])
        vurl = viewer_url(purl, int(c["page_no"]))
        sources.append(PdfSource(
            pdf_id=c["pdf_id"],
            pdf_path=c["pdf_path"],
            page_no=int(c["page_no"]),
            chunk_id=int(c["chunk_id"]),
            chunk_profile=c.get("chunk_profile"),
            pdf_url=purl,
            viewer_url=vurl,
            snippet=(c.get("text") or "")[:400],  # UI용 짧은 근거
        ))

    return AskPdfResponse(answer=msg.content, sources=sources)
