# app/pdf/pdf_loader.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fitz

from app.pdf.quality import QualityPolicy, PageStats, decide_skip, should_skip


@dataclass
class LoadedPage:
    page_no: int
    text: str
    stats: PageStats


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _append_jsonl(path: str, record: Dict[str, Any]) -> None:
    _ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _estimate_image_area_ratio(page: fitz.Page) -> tuple[int, float]:
    """
    외부망 없이 가능한 선에서 "이미지 중심 페이지"를 판별하기 위한 근사치.
    - page.get_images(full=True)로 이미지 존재를 감지
    - page.get_image_rects(xref)로 이미지가 놓인 영역을 얻어 면적 합산
    """
    page_rect = page.rect
    page_area = float(page_rect.width * page_rect.height) if page_rect else 0.0
    if page_area <= 0:
        return 0, 0.0

    images = page.get_images(full=True)
    if not images:
        return 0, 0.0

    total_img_area = 0.0
    for img in images:
        xref = img[0]
        rects = page.get_image_rects(xref)
        for r in rects:
            total_img_area += float(r.width * r.height)

    ratio = min(total_img_area / page_area, 1.0)
    return len(images), ratio


def load_pdf_pages_text(
    pdf_id: str,
    pdf_path: str,
    *,
    policy: Optional[QualityPolicy] = None,
    skip_log_path: str = "logs/skip_pages.jsonl",
    max_pages: Optional[int] = None,
) -> Tuple[List[LoadedPage], Dict[str, Any]]:
    """
    PDF를 페이지 단위로 처리:
    - 텍스트 추출(로컬)
    - 이미지/텍스트 품질 기반으로 스킵 결정
    - 스킵된 페이지는 JSONL로 로그 남김
    반환:
      (keep_pages, summary)
    """
    policy = policy or QualityPolicy()

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    kept: List[LoadedPage] = []
    skipped = 0

    for page_no in range(total_pages):
        page = doc.load_page(page_no)

        # 텍스트 추출(로컬) - 슬라이드형은 순서가 깨질 수 있지만,
        # 여기 단계에서는 "스킵 판별" 목적이므로 일단 raw 텍스트만 확보
        text = page.get_text("text") or ""

        image_count, image_area_ratio = _estimate_image_area_ratio(page)

        stats = decide_skip(
            page_no=page_no,
            text=text,
            image_count=image_count,
            image_area_ratio=image_area_ratio,
            policy=policy,
        )

        if should_skip(stats):
            skipped += 1
            _append_jsonl(
                skip_log_path,
                {
                    "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "pdf_id": pdf_id,
                    "pdf_path": pdf_path,
                    "page_no": page_no,
                    "action": "skip",
                    "reasons": stats.reasons,
                    "metrics": {
                        "text_len": stats.text_len,
                        "line_count": stats.line_count,
                        "short_line_ratio": stats.short_line_ratio,
                        "image_count": stats.image_count,
                        "image_area_ratio": stats.image_area_ratio,
                    },
                },
            )
            continue

        kept.append(LoadedPage(page_no=page_no, text=text.strip(), stats=stats))

    doc.close()

    summary = {
        "pdf_id": pdf_id,
        "pdf_path": pdf_path,
        "pages_total": total_pages,
        "pages_kept": len(kept),
        "pages_skipped": skipped,
        "policy": policy.__dict__,
        "skip_log_path": skip_log_path,
    }
    return kept, summary


def merge_pages_text(pages: List[LoadedPage]) -> str:
    """
    keep된 페이지들의 텍스트를 하나로 합침(다음 단계: 청킹 전에 사용 가능)
    """
    parts: List[str] = []
    for p in pages:
        header = f"\n\n[PAGE {p.page_no}]\n"
        parts.append(header + (p.text or ""))
    return "".join(parts).strip()
