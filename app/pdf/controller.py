# app/pdf/controller.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.pdf.pdf_loader import load_pdf_pages_text
from app.pdf.profile import build_doc_profile
from app.pdf.strategy import choose_chunk_strategy, append_strategy_log
from app.pdf.chunker import chunk_pages
from app.pdf.index_service import index_pdf_chunks
from app.pdf.batch_ingest import ingest_pdf_folder
from app.pdf.schemas import AskPdfRequest, AskPdfResponse
from app.pdf.rag_service import answer_pdf_question
from app.pdf.url_utils import pdf_page_image_url

router = APIRouter(prefix="/pdf", tags=["pdf"])


# -----------------------------
# Request Models
# -----------------------------
class IngestReq(BaseModel):
    pdf_id: str = Field(..., description="ES에 저장될 문서 ID (중복 방지용). 예: 파일명(확장자 제외)")
    pdf_path: str = Field(..., description="PDF 파일 경로. 예: data/pdfs/sample.pdf")


class IngestFolderReq(BaseModel):
    folder_path: str = Field(..., description="PDF/XLSX 파일들이 있는 폴더 경로. 예: data/pdfs")
    max_rows_per_sheet: int | None = Field(
        None,
        description="(XLSX) 시트당 최대 로우 수 제한. None이면 제한 없음",
        ge=1,
    )


# -----------------------------
# Endpoints
# -----------------------------
@router.post("/ingest-folder")
def ingest_folder(req: IngestFolderReq):
    """
    폴더 내 PDF/XLSX를 자동 ingest:
    - PDF: 스킵판별+로그 -> 전략선택 -> 청킹 -> ES 색인
    - XLSX: 시트별 텍스트 변환 -> 청킹 -> ES 색인
    """
    try:
        return ingest_pdf_folder(
            folder_path=req.folder_path,
            max_rows_per_sheet=req.max_rows_per_sheet,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
def ingest_pdf(req: IngestReq):
    """
    단일 PDF ingest:
    - 페이지 텍스트 추출
    - 이미지/저품질 페이지 스킵(로그 남김)
    - 문서 프로파일 기반 chunk 전략 자동 선택
    - 청킹 -> 임베딩 -> ES bulk 색인
    """
    try:
        pages, summary = load_pdf_pages_text(
            pdf_id=req.pdf_id,
            pdf_path=req.pdf_path,
            skip_log_path="logs/skip_pages.jsonl",
        )

        # 1) 문서 프로파일 계산
        profile = build_doc_profile(
            pages,
            pages_total=summary["pages_total"],
            pages_skipped=summary["pages_skipped"],
        )

        # 2) chunk 전략 자동 선택 + 로그
        strategy = choose_chunk_strategy(profile)
        append_strategy_log(
            log_path="logs/chunk_strategy.jsonl",
            pdf_id=req.pdf_id,
            pdf_path=req.pdf_path,
            profile=profile,
            strategy=strategy,
        )

        # 3) keep 페이지들만 청킹(자동 파라미터 적용)
        page_pairs = [(p.page_no, p.text) for p in pages]
        chunks = chunk_pages(
            page_pairs,
            chunk_size=strategy.chunk_size,
            chunk_overlap=strategy.chunk_overlap,
        )

        # 4) ES 색인
        indexed = index_pdf_chunks(
            pdf_id=req.pdf_id,
            pdf_path=req.pdf_path,
            chunks=chunks,
            extra_meta={
                "source_type": "pdf",
                "extract_method": "text_only",
                "pages_total": summary["pages_total"],
                "pages_kept": summary["pages_kept"],
                "pages_skipped": summary["pages_skipped"],
                "chunk_strategy": strategy.name,
                "chunk_size": strategy.chunk_size,
                "chunk_overlap": strategy.chunk_overlap,
                "chunk_strategy_reason": strategy.reason,
            },
        )

        return {
            "pdf_id": req.pdf_id,
            "pdf_path": req.pdf_path,
            "pages_total": summary["pages_total"],
            "pages_kept": summary["pages_kept"],
            "pages_skipped": summary["pages_skipped"],
            "kept_pages_ratio": profile.kept_pages_ratio,
            "avg_text_len_per_kept_page": profile.avg_text_len_per_kept_page,
            "avg_short_line_ratio": profile.avg_short_line_ratio,
            "chunk_strategy": strategy.name,
            "chunk_size": strategy.chunk_size,
            "chunk_overlap": strategy.chunk_overlap,
            "chunks_created": len(chunks),
            "chunks_indexed": indexed,
            "skip_log_path": summary["skip_log_path"],
            "strategy_log_path": "logs/chunk_strategy.jsonl",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/ask", response_model=AskPdfResponse)
def ask_pdf(req: AskPdfRequest):
    result = answer_pdf_question(req.question, top_k=req.top_k, pdf_id=req.pdf_id)

    sources = result["sources"] if isinstance(result, dict) else result.sources

    for s in sources:
        pdf_path = s["pdf_path"] if isinstance(s, dict) else s.pdf_path
        page_no = s["page_no"] if isinstance(s, dict) else s.page_no

        page_img = pdf_page_image_url(pdf_path, page_no, zoom=2.0)

        if isinstance(s, dict):
            s["page_image_url"] = page_img
        else:
            pass

    if not isinstance(result, dict):
        new_sources = []
        for s in result.sources:
            d = s.model_dump()
            d["page_image_url"] = pdf_page_image_url(d["pdf_path"], d["page_no"], zoom=2.0)
            new_sources.append(d)
        return {"answer": result.answer, "sources": new_sources}

    return result
