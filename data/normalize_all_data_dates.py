#!/usr/bin/env python3
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1")
PERIOD_PATTERN = re.compile(r"^(?P<start>\d{6})-(?P<end>\d{6})_")

YEAR_KEYWORDS = {"year", "년도", "연도"}
MONTH_KEYWORDS = {"month", "월"}
DATE_COLUMN_HINTS = ("년", "월", "일", "date", "날짜", "기준", "period", "기간")


@dataclass(slots=True)
class DateColumns:
    year_col: Optional[str] = None
    month_col: Optional[str] = None
    combined_col: Optional[str] = None


def detect_encoding(path: Path) -> str:
    best_encoding: Optional[str] = None
    best_score = -1
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=encoding, nrows=0)
        except Exception:  # noqa: BLE001
            continue
        header = "".join(df.columns.astype(str))
        hangul_score = sum("가" <= ch <= "힣" for ch in header)
        ascii_score = sum(ch.isascii() for ch in header)
        score = hangul_score * 2 + ascii_score
        if score > best_score:
            best_score = score
            best_encoding = encoding
    if best_encoding is None:
        raise ValueError(f"Failed to detect encoding for {path}")
    return best_encoding


def parse_period_from_name(name: str) -> tuple[Optional[int], Optional[int]]:
    match = PERIOD_PATTERN.match(name)
    if not match:
        return None, None
    start = int(match.group("start"))
    year = start // 100
    month = start % 100
    return year, month


def normalize_column_name(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def is_year_series(series: pd.Series) -> bool:
    digits = (
        series.dropna()
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
    )
    if digits.empty:
        return False
    numeric = pd.to_numeric(digits, errors="coerce")
    valid = numeric.between(1900, 2100)
    return valid.mean() >= 0.8


def is_month_series(series: pd.Series) -> bool:
    digits = (
        series.dropna()
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
    )
    if digits.empty:
        return False
    numeric = pd.to_numeric(digits, errors="coerce")
    valid = numeric.between(1, 12)
    return valid.mean() >= 0.8


def detect_date_columns(df: pd.DataFrame) -> DateColumns:
    info = DateColumns()
    for column in df.columns:
        normalized = normalize_column_name(column)
        series = df[column]
        if info.year_col is None and (
            normalized in YEAR_KEYWORDS or normalized.endswith("년도")
        ):
            if is_year_series(series):
                info.year_col = column
                continue
        if info.month_col is None and (
            normalized in MONTH_KEYWORDS or normalized == "기준월"
        ):
            if is_month_series(series):
                info.month_col = column
                continue

    if info.year_col is None or info.month_col is None:
        for column in df.columns:
            normalized = normalize_column_name(column)
            if not any(hint in normalized for hint in DATE_COLUMN_HINTS):
                continue
            series = df[column]
            digits = (
                series.dropna()
                .astype(str)
                .str.replace(r"[^0-9]", "", regex=True)
            )
            if digits.empty:
                continue
            lengths = digits.str.len()
            if not ((lengths >= 6) & (lengths <= 8)).mean() >= 0.6:
                continue
            numeric = pd.to_numeric(digits.str[:6], errors="coerce")
            months = pd.to_numeric(digits.str[4:6], errors="coerce")
            mask = numeric.notna() & months.between(1, 12)
            if mask.mean() >= 0.6:
                info.combined_col = column
                break

    return info


def extract_year_month_from_series(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    values = series.astype(str).str.replace(r"[^0-9]", "", regex=True)
    year = pd.to_numeric(values.str[:4], errors="coerce")
    month = pd.to_numeric(values.str[4:6], errors="coerce")
    valid = year.between(1900, 2100) & month.between(1, 12)
    year = year.where(valid)
    month = month.where(valid)
    return year.astype("Int64"), month.astype("Int64")


def ensure_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def determine_year_month(
    df: pd.DataFrame,
    info: DateColumns,
    fallback_year: Optional[int],
    fallback_month: Optional[int],
) -> tuple[pd.Series, pd.Series, list[str]]:
    related_columns: list[str] = []
    year_series: Optional[pd.Series] = None
    month_series: Optional[pd.Series] = None

    if info.year_col:
        year_series = ensure_int_series(df[info.year_col])
        related_columns.append(info.year_col)
    if info.month_col:
        month_series = ensure_int_series(df[info.month_col])
        related_columns.append(info.month_col)

    if (year_series is None or month_series is None) and info.combined_col:
        combined_year, combined_month = extract_year_month_from_series(df[info.combined_col])
        related_columns.append(info.combined_col)
        if year_series is None:
            year_series = combined_year
        if month_series is None:
            month_series = combined_month

    if year_series is None:
        if fallback_year is None:
            year_values = pd.Series(np.nan, index=df.index, dtype="float")
        else:
            year_values = pd.Series(fallback_year, index=df.index, dtype="float")
        year_series = year_values.astype("Int64")

    if month_series is None:
        if fallback_month is None:
            month_values = pd.Series(np.nan, index=df.index, dtype="float")
        else:
            month_values = pd.Series(fallback_month, index=df.index, dtype="float")
        month_series = month_values.astype("Int64")

    return year_series, month_series, related_columns


def process_file(path: Path) -> bool:
    encoding = detect_encoding(path)
    df = pd.read_csv(path, encoding=encoding)

    fallback_year, fallback_month = parse_period_from_name(path.name)
    info = detect_date_columns(df)
    year_series, month_series, related_columns = determine_year_month(
        df,
        info,
        fallback_year,
        fallback_month,
    )

    df["year"] = year_series
    df["month"] = month_series

    order = ["year", "month"]
    seen = set(order)
    for column in related_columns:
        if column in ("year", "month"):
            continue
        if column not in seen and column in df.columns:
            order.append(column)
            seen.add(column)

    for column in df.columns:
        if column not in seen:
            order.append(column)
            seen.add(column)

    df = df[order]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return True


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    root = base_dir / "data_csv_type" / "데이터랩" / "all_data"
    if not root.exists():
        raise SystemExit(f"Target directory not found: {root}")

    folders = [root / str(i) for i in range(1, 8)]
    processed = 0
    for folder in folders:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.csv")):
            process_file(path)
            processed += 1

    print(f"Processed {processed} files.")


if __name__ == "__main__":
    main()

