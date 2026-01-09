# app/xlsx/xlsx_loader.py
from __future__ import annotations

import pandas as pd
from dataclasses import dataclass
from typing import List


@dataclass
class SheetText:
    sheet_name: str
    text: str


def load_xlsx_text(
    xlsx_path: str,
    *,
    max_rows_per_sheet: int | None = None,
) -> List[SheetText]:
    """
    XLSX를 시트별 텍스트로 변환
    """
    xls = pd.ExcelFile(xlsx_path)
    results: List[SheetText] = []

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)

        if df.empty:
            continue

        # 컬럼명 정리
        df.columns = [str(c).strip() for c in df.columns]

        if max_rows_per_sheet:
            df = df.head(max_rows_per_sheet)

        lines = []
        for _, row in df.iterrows():
            items = []
            for col, val in row.items():
                if pd.isna(val):
                    continue
                items.append(f"{col}={val}")
            if items:
                lines.append(" | ".join(items))

        if lines:
            text = f"[SHEET: {sheet_name}]\n" + "\n".join(lines)
            results.append(SheetText(sheet_name=sheet_name, text=text))

    return results
