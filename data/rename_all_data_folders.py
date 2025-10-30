#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

PERIOD_PATTERN = re.compile(r"(\d{6}-\d{6})")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    target_dir = base_dir / "data_csv_type" / "데이터랩" / "all_data"
    if not target_dir.exists():
        raise SystemExit(f"Target directory not found: {target_dir}")

    folders = [path for path in sorted(target_dir.iterdir()) if path.is_dir()]
    if not folders:
        print("No folders to rename.")
        return

    period_groups: dict[str, list[Path]] = defaultdict(list)
    for folder in folders:
        match = PERIOD_PATTERN.search(folder.name)
        if not match:
            raise SystemExit(f"Unable to detect period in folder name: {folder.name}")
        period_groups[match.group(1)].append(folder)

    # Keep summary for reporting
    operations: list[tuple[Path, Path]] = []

    for period, paths in period_groups.items():
        for index, path in enumerate(sorted(paths, key=lambda p: p.name), start=1):
            new_name = f"{period}_{index}"
            new_path = target_dir / new_name
            if path.name == new_name:
                continue
            if new_path.exists():
                raise SystemExit(f"Target folder already exists: {new_path}")
            path.rename(new_path)
            operations.append((path, new_path))

    if operations:
        print("Renamed folders:")
        for old_path, new_path in operations:
            print(f"- {old_path.name} -> {new_path.name}")
    else:
        print("All folders already conform to the naming scheme.")


if __name__ == "__main__":
    main()

