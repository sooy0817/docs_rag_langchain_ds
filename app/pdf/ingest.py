# app/pdf/controller.py (ingest 부분만 예시)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.pdf.pdf_loader import load_pdf_pages_text
from app.pdf.chunker import chunk_pages
from app.pdf.index_service import index_pdf_chunks

router = APIRouter(prefix="/pdf", tags=["pdf"])


class IngestReq(BaseModel):
    pdf_id: str
    pdf_path: str


@router.post("/ingest")
def ingest_pdf(req: IngestReq):
    try:
        pages, summary = load_pdf_pages_text(
            pdf_id=req.pdf_id,
            pdf_path=req.pdf_path,
            skip_log_path="logs/skip_pages.jsonl",
        )

        # keep 페이지들만 청킹
        page_pairs = [(p.page_no, p.text) for p in pages]
        chunks = chunk_pages(page_pairs, chunk_size=1000, chunk_overlap=150)

        indexed = index_pdf_chunks(
            pdf_id=req.pdf_id,
            pdf_path=req.pdf_path,
            chunks=chunks,
            extra_meta={
                "extract_method": "text_only",
                "pages_kept": summary["pages_kept"],
                "pages_skipped": summary["pages_skipped"],
            },
        )

        return {
            "pdf_id": req.pdf_id,
            "pages_total": summary["pages_total"],
            "pages_kept": summary["pages_kept"],
            "pages_skipped": summary["pages_skipped"],
            "chunks_created": len(chunks),
            "chunks_indexed": indexed,
            "skip_log_path": summary["skip_log_path"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
