# app/pdf/profile.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from app.pdf.pdf_loader import LoadedPage


@dataclass(frozen=True)
class DocProfile:
    pages_kept: int
    pages_skipped: int
    pages_total: int

    avg_text_len_per_kept_page: float
    avg_short_line_ratio: float
    kept_pages_ratio: float  # kept / total

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_doc_profile(
    kept_pages: List[LoadedPage],
    *,
    pages_total: int,
    pages_skipped: int,
) -> DocProfile:
    pages_kept = len(kept_pages)

    if pages_kept == 0:
        avg_text_len = 0.0
        avg_short_ratio = 1.0
    else:
        avg_text_len = sum(p.stats.text_len for p in kept_pages) / pages_kept
        avg_short_ratio = sum(p.stats.short_line_ratio for p in kept_pages) / pages_kept

    total = max(int(pages_total), 1)
    kept_ratio = pages_kept / total

    return DocProfile(
        pages_kept=pages_kept,
        pages_skipped=int(pages_skipped),
        pages_total=int(pages_total),
        avg_text_len_per_kept_page=float(avg_text_len),
        avg_short_line_ratio=float(avg_short_ratio),
        kept_pages_ratio=float(kept_ratio),
    )
