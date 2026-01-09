from __future__ import annotations
import os
from urllib.parse import quote

def pdf_page_image_url(pdf_path: str, page_no: int, zoom: float = 2.0) -> str:
    filename = os.path.basename(pdf_path.replace("\\", "/"))
    return f"/pdf/page-image?file={quote(filename)}&page_no={page_no}&zoom={zoom}"

def pdf_url_from_path(pdf_path: str) -> str:
    # 윈도우/리눅스 경로 모두 대응: basename만 추출
    filename = os.path.basename(pdf_path.replace("\\", "/"))
    return f"/files/pdfs/{quote(filename)}"

def viewer_url(pdf_url: str, page_no: int) -> str:
    # 대부분의 PDF 뷰어는 #page= 를 1부터 인식
    return f"{pdf_url}#page={page_no + 1}"
