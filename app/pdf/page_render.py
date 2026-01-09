from __future__ import annotations

import os
from urllib.parse import unquote
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import fitz  # PyMuPDF

router = APIRouter(prefix="/pdf", tags=["pdf"])

PDF_DIR = os.path.abspath("data/pdfs")

def _safe_join_pdf(filename: str) -> str:
    # URL 인코딩된 파일명 대응
    filename = unquote(filename)
    filename = filename.replace("\\", "/")
    base = os.path.basename(filename)  # 디렉토리 탈출 방지
    path = os.path.join(PDF_DIR, base)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"PDF not found: {base}")
    return path

@router.get("/page-image")
def pdf_page_image(file: str, page_no: int, zoom: float = 2.0):
    """
    file: PDF 파일명 (예: '데이타솔루션 복리후생 제도_2023년.pdf')
    page_no: 0-based
    zoom: 해상도(2.0 ~ 3.0 추천)
    """
    if page_no < 0:
        raise HTTPException(status_code=400, detail="page_no must be >= 0")

    pdf_path = _safe_join_pdf(file)

    try:
        doc = fitz.open(pdf_path)
        if page_no >= doc.page_count:
            raise HTTPException(status_code=400, detail=f"page_no out of range (0~{doc.page_count-1})")

        page = doc.load_page(page_no)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)  # PNG
        img_bytes = pix.tobytes("png")
        doc.close()
        return Response(content=img_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
