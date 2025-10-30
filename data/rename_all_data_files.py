#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    target_dir = base_dir / "data_csv_type" / "데이터랩" / "all_data"
    if not target_dir.exists():
        raise SystemExit(f"Target directory not found: {target_dir}")

    operations: list[tuple[Path, Path]] = []

    for folder in sorted(target_dir.iterdir()):
        if not folder.is_dir():
            continue
        try:
            period, _ = folder.name.split("_", 1)
        except ValueError:
            print(f"Skipping folder without expected suffix: {folder.name}")
            continue

        prefix = f"{period}_"

        for file_path in sorted(folder.iterdir()):
            if not file_path.is_file():
                continue
            name = file_path.name
            if "_" not in name:
                continue
            suffix = name.split("_", 1)[1]
            new_name = prefix + suffix
            if new_name == name:
                continue
            new_path = file_path.with_name(new_name)
            if new_path.exists():
                raise SystemExit(f"Target file already exists: {new_path}")
            file_path.rename(new_path)
            operations.append((file_path, new_path))

    if operations:
        print(f"Renamed {len(operations)} files.")
    else:
        print("No files required renaming.")


if __name__ == "__main__":
    main()

