# app/pdf/schemas.py
from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional

class PdfSource(BaseModel):
    pdf_id: str
    pdf_path: str
    page_no: int
    chunk_id: int
    chunk_profile: Optional[str] = None
    page_image_url: Optional[str] = None

    pdf_url: str
    viewer_url: str
    snippet: Optional[str] = None

class AskPdfRequest(BaseModel):
    question: str
    top_k: int = 10
    pdf_id: Optional[str] = None

class AskPdfResponse(BaseModel):
    answer: str
    sources: List[PdfSource]
