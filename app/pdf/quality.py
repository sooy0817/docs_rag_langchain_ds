# app/pdf/quality.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class PageStats:
    page_no: int
    text_len: int
    line_count: int
    short_line_ratio: float
    image_count: int
    image_area_ratio: float

    # decide_skip에서 계산된 플래그(원인)들
    flags: List[str]

    # should_skip에서 최종 스킵으로 판정된 이유
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityPolicy:
    """
    운영 최적화 목적:
    - 슬라이드/배경이미지 PDF에서 image_area_ratio가 높게 나와도,
      텍스트가 충분하면 KEEP
    - 실제로 의미 없는 페이지(표지/배경/스캔이미지)는 (image_heavy + low_text)로 스킵
    """

    # 1) low text 후보
    # 기존 200은 "텍스트가 있는데도 low_text"를 자주 만들 수 있어 완화
    min_text_len: int = 120

    # 2) 텍스트 충분하면 무조건 KEEP override (가장 중요)
    keep_text_len_override: int = 180
    keep_line_count_override: int = 6  # 줄 수로도 override

    # 3) fragmented(슬라이드 조각 텍스트) 판별: "스킵"보다는 참고용
    max_short_line_ratio: float = 0.70
    short_line_max_len: int = 6

    # 4) 이미지 중심 페이지 판별
    # 기존 0.55는 너무 민감. 슬라이드 배경이면 거의 1.0도 흔함.
    min_image_area_ratio_to_consider: float = 0.75
    min_image_count_to_consider: int = 1

    # 5) 최종 스킵 로직(중요)
    # image_heavy 단독 스킵 금지
    skip_image_only: bool = False

    # 기본 스킵 조건: (image_heavy AND low_text)
    # 스캔/표지/배경페이지를 잘 걸러냄
    skip_if_image_heavy_and_low_text: bool = True

    # fragmented_text는 기본적으로 스킵에 쓰지 않음(운영하면서 필요 시 조정)
    skip_if_fragmented_text_only: bool = False
    skip_if_image_heavy_and_fragmented_text_and_low_text: bool = True


def compute_short_line_ratio(text: str, short_max_len: int) -> tuple[int, int, float]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return 0, 0, 0.0

    short_lines = sum(1 for ln in lines if len(ln) <= short_max_len)
    ratio = short_lines / max(len(lines), 1)
    return len(lines), short_lines, ratio


def decide_skip(
    *,
    page_no: int,
    text: str,
    image_count: int,
    image_area_ratio: float,
    policy: Optional[QualityPolicy] = None,
) -> PageStats:
    policy = policy or QualityPolicy()

    text = text or ""
    text_len = len(text)
    line_count, _, short_line_ratio = compute_short_line_ratio(text, policy.short_line_max_len)

    flags: List[str] = []

    # ---- 원인 플래그 계산 ----
    low_text = text_len < policy.min_text_len
    if low_text:
        flags.append("low_text")

    fragmented_text = (line_count > 0 and short_line_ratio >= policy.max_short_line_ratio)
    if fragmented_text:
        flags.append("fragmented_text")

    image_heavy = (
        image_count >= policy.min_image_count_to_consider
        and image_area_ratio >= policy.min_image_area_ratio_to_consider
    )
    if image_heavy:
        flags.append("image_heavy")

    # ---- 텍스트 우선 KEEP override ----
    # 슬라이드/배경이미지라도, 텍스트가 충분하면 살린다.
    # (text_len 또는 line_count 중 하나만 넘어도 KEEP)
    if (text_len >= policy.keep_text_len_override) or (line_count >= policy.keep_line_count_override):
        return PageStats(
            page_no=page_no,
            text_len=text_len,
            line_count=line_count,
            short_line_ratio=float(short_line_ratio),
            image_count=image_count,
            image_area_ratio=float(image_area_ratio),
            flags=flags,
            reasons=[],  # KEEP
        )

    # ---- 최종 스킵 reasons 결정 (정책 기반) ----
    reasons: List[str] = []

    # 1) image_heavy 단독 스킵은 기본적으로 금지
    if image_heavy and policy.skip_image_only:
        reasons.append("image_heavy")

    # 2) 기본 스킵: (image_heavy AND low_text)
    if policy.skip_if_image_heavy_and_low_text and image_heavy and low_text:
        reasons.extend(["image_heavy", "low_text"])

    # 3) fragmented_text 단독 스킵(기본 False)
    if policy.skip_if_fragmented_text_only and fragmented_text:
        reasons.append("fragmented_text")

    # 4) (image_heavy AND low_text AND fragmented_text)일 때만 더 강하게 스킵 표시
    #    (이미 2)에서 스킵되지만, 사유에 fragmented_text까지 남기고 싶을 때 유용)
    if policy.skip_if_image_heavy_and_fragmented_text_and_low_text and image_heavy and low_text and fragmented_text:
        if "fragmented_text" not in reasons:
            reasons.append("fragmented_text")

    # 중복 제거(순서 유지)
    dedup: List[str] = []
    for r in reasons:
        if r not in dedup:
            dedup.append(r)

    return PageStats(
        page_no=page_no,
        text_len=text_len,
        line_count=line_count,
        short_line_ratio=float(short_line_ratio),
        image_count=image_count,
        image_area_ratio=float(image_area_ratio),
        flags=flags,        # 참고용(로그/분석)
        reasons=dedup,      # should_skip에서 사용
    )


def should_skip(stats: PageStats) -> bool:
    # 최종 reasons가 있으면 스킵
    return len(stats.reasons) > 0
