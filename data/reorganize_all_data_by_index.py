#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

FOLDER_PATTERN = re.compile(r"^(?P<period>\d{6}-\d{6})_(?P<index>\d+)$")
VALID_INDICES = {str(i) for i in range(1, 8)}


def ensure_destination_dirs(root: Path) -> dict[str, Path]:
    destinations: dict[str, Path] = {}
    for idx in sorted(VALID_INDICES, key=int):
        dest = root / idx
        dest.mkdir(parents=True, exist_ok=True)
        destinations[idx] = dest
    return destinations


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    all_data_dir = base_dir / "data_csv_type" / "데이터랩" / "all_data"
    if not all_data_dir.exists():
        raise SystemExit(f"Target directory not found: {all_data_dir}")

    destinations = ensure_destination_dirs(all_data_dir)

    to_remove: list[Path] = []
    moved_count = 0

    for entry in sorted(all_data_dir.iterdir()):
        if not entry.is_dir():
            continue
        match = FOLDER_PATTERN.match(entry.name)
        if not match:
            if entry.name in destinations:
                # already a destination directory
                continue
            raise SystemExit(f"Unexpected directory format: {entry.name}")

        index = match.group("index")
        if index not in VALID_INDICES:
            raise SystemExit(f"Unsupported index '{index}' in folder {entry.name}")

        dest_dir = destinations[index]

        for item in sorted(entry.iterdir()):
            if item.is_dir():
                raise SystemExit(f"Nested directory found inside {entry}: {item.name}")
            target_path = dest_dir / item.name
            if target_path.exists():
                raise SystemExit(f"Cannot move {item} -> {target_path}: target exists")
            item.rename(target_path)
            moved_count += 1

        to_remove.append(entry)

    for folder in to_remove:
        folder.rmdir()

    print(f"Moved {moved_count} files into index-based folders.")
    if to_remove:
        print(f"Removed {len(to_remove)} empty period folders.")


if __name__ == "__main__":
    main()

