# app/pdf/batch_ingest.py
from __future__ import annotations

import os
from typing import Dict, List

from app.pdf.pdf_loader import load_pdf_pages_text
from app.pdf.profile import build_doc_profile
from app.pdf.strategy import choose_chunk_strategy, append_strategy_log
from app.pdf.chunker import chunk_pages
from app.pdf.index_service import index_pdf_chunks

from app.xlsx.xlsx_loader import load_xlsx_text


def ingest_pdf_folder(
    folder_path: str,
    *,
    skip_log_path: str = "logs/skip_pages.jsonl",
    strategy_log_path: str = "logs/chunk_strategy.jsonl",
    max_rows_per_sheet: int | None = None,  # xlsx 옵션
) -> List[Dict]:
    """
    하나의 폴더 아래 PDF/XLSX를 자동 ingest
    - PDF: 스킵판별+로그 -> 전략선택 -> 청킹 -> ES 색인
    - XLSX: 시트별 텍스트 변환 -> 전략선택(간단) -> 청킹 -> ES 색인
    """
    results: List[Dict] = []

    for filename in sorted(os.listdir(folder_path)):
        lower = filename.lower()
        if not (lower.endswith(".pdf") or lower.endswith(".xlsx")):
            continue

        path = os.path.join(folder_path, filename)
        doc_id = os.path.splitext(filename)[0]  # 한글 OK

        # -------------------------
        # PDF ingest
        # -------------------------
        if lower.endswith(".pdf"):
            try:
                pages, summary = load_pdf_pages_text(
                    pdf_id=doc_id,
                    pdf_path=path,
                    skip_log_path=skip_log_path,
                )

                profile = build_doc_profile(
                    pages,
                    pages_total=summary["pages_total"],
                    pages_skipped=summary["pages_skipped"],
                )

                strategy = choose_chunk_strategy(profile)
                append_strategy_log(
                    log_path=strategy_log_path,
                    pdf_id=doc_id,
                    pdf_path=path,
                    profile=profile,
                    strategy=strategy,
                )

                page_pairs = [(p.page_no, p.text) for p in pages]
                chunks = chunk_pages(
                    page_pairs,
                    chunk_size=strategy.chunk_size,
                    chunk_overlap=strategy.chunk_overlap,
                )

                indexed = index_pdf_chunks(
                    pdf_id=doc_id,
                    pdf_path=path,
                    chunks=chunks,
                    extra_meta={
                        "source_type": "pdf",
                        "extract_method": "text_only",
                        "chunk_strategy": "character_recursive",
                        "chunk_profile": strategy.name,
                        "chunk_profile_reason": strategy.reason,
                        "chunk_size": strategy.chunk_size,
                        "chunk_overlap": strategy.chunk_overlap,
                        "pages_total": summary["pages_total"],
                        "pages_kept": summary["pages_kept"],
                        "pages_skipped": summary["pages_skipped"],
                    },
                )

                results.append({
                    "doc_id": doc_id,
                    "file": filename,
                    "type": "pdf",
                    "pages_total": summary["pages_total"],
                    "pages_kept": summary["pages_kept"],
                    "pages_skipped": summary["pages_skipped"],
                    "chunks_created": len(chunks),
                    "chunks_indexed": indexed,
                    "status": "success",
                })

            except Exception as e:
                results.append({
                    "doc_id": doc_id,
                    "file": filename,
                    "type": "pdf",
                    "status": "error",
                    "error": str(e),
                })

        # -------------------------
        # XLSX ingest
        # -------------------------
        elif lower.endswith(".xlsx"):
            try:
                sheets = load_xlsx_text(
                    path,
                    max_rows_per_sheet=max_rows_per_sheet,
                )

                # 시트별 텍스트를 "페이지"처럼 취급해서 chunker 재사용
                page_pairs = []
                for i, s in enumerate(sheets):
                    # 텍스트 안에 시트명을 포함시켜 근거를 명확히 함
                    text = f"[SHEET: {s.sheet_name}]\n{s.text}"
                    page_pairs.append((i, text))

                # XLSX는 프로파일/전략을 간단히 결정 (시트 텍스트 길이 기반)
                # - 너무 거대하면 chunk_size 조금 키우고
                # - 기본은 혼합형으로 둠
                total_len = sum(len(t) for _, t in page_pairs)
                if total_len >= 200_000:
                    chunk_size, chunk_overlap, strat_name = 1300, 180, "xlsx_large"
                elif total_len <= 30_000:
                    chunk_size, chunk_overlap, strat_name = 800, 150, "xlsx_small"
                else:
                    chunk_size, chunk_overlap, strat_name = 1000, 180, "xlsx_default"

                chunks = chunk_pages(
                    page_pairs,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )

                indexed = index_pdf_chunks(
                    pdf_id=doc_id,
                    pdf_path=path,
                    chunks=chunks,
                    extra_meta={
                        "source_type": "xlsx",
                        "extract_method": "sheet_text",
                        "chunk_strategy": "character_recursive",
                        "chunk_profile": strat_name,
                        "chunk_profile_reason": f"total_len={total_len}",
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "sheets_count": len(sheets),
                    },
                )

                results.append({
                    "doc_id": doc_id,
                    "file": filename,
                    "type": "xlsx",
                    "sheets_count": len(sheets),
                    "chunks_created": len(chunks),
                    "chunks_indexed": indexed,
                    "status": "success",
                })

            except Exception as e:
                results.append({
                    "doc_id": doc_id,
                    "file": filename,
                    "type": "xlsx",
                    "status": "error",
                    "error": str(e),
                })

    return results
