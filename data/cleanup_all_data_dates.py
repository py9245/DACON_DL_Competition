#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATE_KEYWORDS = ("년", "월", "일", "date", "날짜", "일자", "기간", "기준", "period")
ALLOWED = {"year", "month"}


def detect_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"):
        try:
            pd.read_csv(path, encoding=encoding, nrows=0)
            return encoding
        except Exception:  # noqa: BLE001
            continue
    raise ValueError(f"Failed to detect encoding for {path}")


def should_drop(column: str) -> bool:
    normalized = re.sub(r"\s+", "", column).lower()
    if normalized in ALLOWED:
        return False
    return any(keyword in normalized for keyword in DATE_KEYWORDS)


def process_file(path: Path) -> bool:
    encoding = detect_encoding(path)
    df = pd.read_csv(path, encoding=encoding)
    drop_cols = [col for col in df.columns if should_drop(col)]

    keep_cols = [col for col in df.columns if col not in drop_cols]
    new_columns = []
    for col in keep_cols:
        if col == "year" or col == "month":
            new_columns.append(col)
    for col in keep_cols:
        if col not in ("year", "month"):
            new_columns.append(col)

    df = df[new_columns]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return True


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    root = base_dir / "data_csv_type" / "데이터랩" / "all_data"
    if not root.exists():
        raise SystemExit(f"Target directory not found: {root}")

    processed = 0
    for path in sorted(root.rglob("*.csv")):
        process_file(path)
        processed += 1

    print(f"Cleaned {processed} files.")


if __name__ == "__main__":
    main()

