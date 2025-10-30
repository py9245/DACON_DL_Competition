#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

BASE_START = 202001
BASE_END = 202509
ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1")
PERIOD_PATTERN = re.compile(r"^(?P<start>\d{6})-(?P<end>\d{6})_")
DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(20\d{2})[-./]?(0[1-9]|1[0-2])"),
    re.compile(r"(20\d{2})\D(1[0-2]|0?[1-9])"),
)


def iterate_months(start: int, end: int) -> list[int]:
    months: list[int] = []
    year = start // 100
    month = start % 100
    end_year = end // 100
    end_month = end % 100
    while (year < end_year) or (year == end_year and month <= end_month):
        months.append(year * 100 + month)
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


BASE_MONTHS = set(iterate_months(BASE_START, BASE_END))


def detect_encoding(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            pd.read_csv(path, encoding=encoding, nrows=0)
            return encoding
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise ValueError(f"Failed to detect encoding for {path}: {last_error}")


def month_int_to_label(value: int) -> str:
    year = value // 100
    month = value % 100
    return f"{year:04d}-{month:02d}"


def months_to_ranges(months: Iterable[int], max_segments: int = 6) -> str:
    values = sorted(set(months))
    if not values:
        return ""

    segments: list[tuple[int, int]] = []
    start = prev = values[0]
    for current in values[1:]:
        expected = (prev // 100) * 100 + ((prev % 100) + 1)
        if prev % 100 == 12:
            expected = (prev // 100 + 1) * 100 + 1
        if current == expected:
            prev = current
            continue
        segments.append((start, prev))
        start = prev = current
    segments.append((start, prev))

    labels: list[str] = []
    for seg_start, seg_end in segments[:max_segments]:
        if seg_start == seg_end:
            labels.append(month_int_to_label(seg_start))
        else:
            labels.append(f"{month_int_to_label(seg_start)}~{month_int_to_label(seg_end)}")

    if len(segments) > max_segments:
        labels.append("…")

    return ", ".join(labels)


def extract_year_months(df: pd.DataFrame) -> set[int]:
    months: set[int] = set()
    if {"년도", "월"}.issubset(df.columns):
        year = pd.to_numeric(df["년도"], errors="coerce")
        month = pd.to_numeric(df["월"], errors="coerce")
        mask = year.notna() & month.notna()
        if mask.any():
            valid_years = year[mask].astype(int)
            valid_months = month[mask].astype(int)
            valid_mask = (
                (valid_years >= 2000)
                & (valid_years <= 2030)
                & (valid_months >= 1)
                & (valid_months <= 12)
            )
            combos = valid_years[valid_mask] * 100 + valid_months[valid_mask]
            months.update(combos.tolist())

    for column in df.columns:
        series = df[column].dropna().astype(str)
        for value in series:
            for pattern in DATE_PATTERNS:
                for match in pattern.finditer(value):
                    year = int(match.group(1))
                    month = int(match.group(2))
                    if not (2000 <= year <= 2030):
                        continue
                    if month < 1 or month > 12:
                        continue
                    months.add(year * 100 + month)

    return months


def parse_period_from_name(name: str) -> tuple[Optional[int], Optional[int]]:
    match = PERIOD_PATTERN.match(name)
    if not match:
        return None, None
    start = int(match.group("start"))
    end = int(match.group("end"))
    return start, end


@dataclass(slots=True)
class FileSummary:
    file_name: str
    folder: str
    data_range: str
    present_count: int
    missing_count: int
    missing_ranges: str
    notes: str


def summarize_file(path: Path) -> FileSummary:
    try:
        encoding = detect_encoding(path)
        df = pd.read_csv(path, encoding=encoding)
    except Exception as exc:  # noqa: BLE001
        return FileSummary(
            file_name=path.name,
            folder=path.parent.name,
            data_range="",
            present_count=0,
            missing_count=len(BASE_MONTHS),
            missing_ranges="",
            notes=f"read_error:{exc}",
        )

    year_months = extract_year_months(df)
    present = sorted(value for value in year_months if BASE_START <= value <= BASE_END)

    outside = sorted(
        value for value in year_months if value < BASE_START or value > BASE_END
    )
    missing = sorted(BASE_MONTHS.difference(present))

    start = month_int_to_label(min(year_months)) if year_months else ""
    end = month_int_to_label(max(year_months)) if year_months else ""
    data_range = f"{start}~{end}".strip("~")
    if not data_range:
        name_start, name_end = parse_period_from_name(path.name)
        if name_start and name_end:
            data_range = f"{month_int_to_label(name_start)}~{month_int_to_label(name_end)}"

    notes: list[str] = []
    if not year_months:
        notes.append("기간 정보 확인 불가")
    if outside:
        notes.append(
            f"기준 외 {len(outside)}개월 (예: {month_int_to_label(outside[0])})"
        )

    missing_ranges = months_to_ranges(missing)
    return FileSummary(
        file_name=path.name,
        folder=path.parent.name,
        data_range=data_range,
        present_count=len(present),
        missing_count=len(missing),
        missing_ranges=missing_ranges,
        notes=", ".join(notes),
    )


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    target_dir = base_dir / "data_csv_type" / "내외국인"
    if not target_dir.exists():
        raise SystemExit(f"Target directory not found: {target_dir}")

    csv_files = sorted(target_dir.glob("*.csv"))
    summaries = [summarize_file(path) for path in csv_files]

    result_dir = target_dir / "result"
    result_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame([asdict(summary) for summary in summaries])
    csv_path = result_dir / "기간누락_요약.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    md_lines: list[str] = []
    md_lines.append("# 기간 누락 점검 (2020-01 ~ 2025-09)")
    md_lines.append("")
    md_lines.append("- 기준 기간: 2020년 1월 ~ 2025년 9월 (총 69개월)")
    md_lines.append(f"- 분석 대상 파일 수: {len(csv_files)}개")
    md_lines.append("- `누락 개월수`가 69이면 기준 기간 데이터를 포함하지 않는 파일입니다.")
    md_lines.append("")
    md_lines.append("| 파일명 | 데이터 범위 | 확보 개월수 | 누락 개월수 | 주요 누락 구간 | 비고 |")
    md_lines.append("| --- | --- | ---: | ---: | --- | --- |")

    for summary in sorted(summaries, key=lambda x: x.missing_count, reverse=True):
        md_lines.append(
            f"| {summary.file_name} | {summary.data_range or '-'} | "
            f"{summary.present_count} | {summary.missing_count} | "
            f"{summary.missing_ranges or '-'} | {summary.notes or '-'} |"
        )

    md_path = result_dir / "기간누락_요약.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8-sig")

    print(f"Wrote summary for {len(csv_files)} files.")
    print(f"- CSV: {csv_path}")
    print(f"- Markdown: {md_path}")


if __name__ == "__main__":
    main()
