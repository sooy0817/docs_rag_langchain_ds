# app/pdf/strategy.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Tuple

from app.pdf.profile import DocProfile


@dataclass(frozen=True)
class ChunkStrategy:
    name: str
    chunk_size: int
    chunk_overlap: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def choose_chunk_strategy(profile: DocProfile) -> ChunkStrategy:
    """
    자동 전략 선택(초기 룰):
    - 연속 텍스트형: 평균 텍스트 길이↑, 짧은 줄 비율↓, kept 비율↑
    - 조각/슬라이드형: 평균 텍스트 길이↓ 또는 짧은 줄 비율↑
    - 혼합형: 그 중간
    """
    avg_len = profile.avg_text_len_per_kept_page
    short_ratio = profile.avg_short_line_ratio
    kept_ratio = profile.kept_pages_ratio

    # 1) 연속 텍스트형(보고서/계약서에 가까움)
    if kept_ratio >= 0.75 and avg_len >= 900 and short_ratio <= 0.35:
        return ChunkStrategy(
            name="continuous_text",
            chunk_size=1200,
            chunk_overlap=150,
            reason=f"kept_ratio={kept_ratio:.2f}, avg_len={avg_len:.0f}, short_ratio={short_ratio:.2f}",
        )

    # 2) 조각/슬라이드형(문장/줄이 잘게 쪼개진 편)
    # (이미지 많은 페이지는 스킵했더라도, 텍스트 박스가 많은 PDF는 kept로 남을 수 있음)
    if avg_len < 550 or short_ratio >= 0.55:
        return ChunkStrategy(
            name="fragmented_text",
            chunk_size=700,
            chunk_overlap=220,
            reason=f"kept_ratio={kept_ratio:.2f}, avg_len={avg_len:.0f}, short_ratio={short_ratio:.2f}",
        )

    # 3) 혼합형(기본값)
    return ChunkStrategy(
        name="mixed_default",
        chunk_size=1000,
        chunk_overlap=180,
        reason=f"kept_ratio={kept_ratio:.2f}, avg_len={avg_len:.0f}, short_ratio={short_ratio:.2f}",
    )


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def append_strategy_log(
    *,
    log_path: str,
    pdf_id: str,
    pdf_path: str,
    profile: DocProfile,
    strategy: ChunkStrategy,
) -> None:
    _ensure_dir(os.path.dirname(log_path))
    record: Dict[str, Any] = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "pdf_id": pdf_id,
        "pdf_path": pdf_path,
        "profile": profile.to_dict(),
        "strategy": strategy.to_dict(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
