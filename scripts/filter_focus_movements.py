"""
Step 1: Filter ART500K to five target movements, keeping only single-label paintings with at least one tag.
Requires raw data (not included in submission); outputs saved to raw_data_eda/.
Inputs: data/label_list.tsv, data/head_info.csv
Outputs: data/filtered_5movements_with_tags.tsv, filtered_5movements_counts.csv, filtered_5movements_tag_counts.csv
"""

from __future__ import annotations

import ast
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
HEAD_INFO_PATH = DATA_DIR / "head_info.csv"
LABEL_LIST_PATH = DATA_DIR / "label_list.tsv"

FILTERED_DATA_PATH = DATA_DIR / "filtered_5movements_with_tags.tsv"
MOVEMENT_COUNTS_PATH = DATA_DIR / "filtered_5movements_counts.csv"
TAG_COUNTS_PATH = DATA_DIR / "filtered_5movements_tag_counts.csv"

TARGET_MOVEMENTS = {
    "Northern Renaissance",
    "Baroque",
    "Romanticism",
    "Impressionism",
    "Cubism",
}


def load_columns() -> list[str]:
    """Read the column name list stored in head_info.csv."""
    with HEAD_INFO_PATH.open(encoding="utf-8") as file:
        return list(ast.literal_eval(file.read().strip()))


def split_tags(raw_tag: str) -> list[str]:
    """Split a raw tag string on semicolons, commas, or pipes into individual tags."""
    return [part.strip() for part in re.split(r"[;,|]", raw_tag) if part.strip()]


def main() -> None:
    columns = load_columns()
    art_movement_idx = columns.index("Art Movement")
    tag_idx = columns.index("Tag") if "Tag" in columns else columns.index("tags")

    movement_counts: Counter[str] = Counter()
    movement_tag_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)

    with (
        LABEL_LIST_PATH.open(newline="", encoding="utf-8") as source,
        FILTERED_DATA_PATH.open("w", newline="", encoding="utf-8") as filtered,
    ):
        reader = csv.reader(source, delimiter="\t")
        writer = csv.writer(filtered, delimiter="\t")
        writer.writerow(columns)

        for row in reader:
            if len(row) <= max(art_movement_idx, tag_idx):
                continue

            movement = row[art_movement_idx].strip()
            tag_value = row[tag_idx].strip()

            if not tag_value:
                continue
            if movement not in TARGET_MOVEMENTS:
                continue
            if "," in movement:
                continue

            writer.writerow(row)
            movement_counts[movement] += 1

            for tag in split_tags(tag_value):
                movement_tag_counts[movement][tag] += 1

    with MOVEMENT_COUNTS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["art_movement", "tagged_paintings", "unique_tags"])
        for movement in sorted(TARGET_MOVEMENTS):
            writer.writerow(
                [
                    movement,
                    movement_counts[movement],
                    len(movement_tag_counts[movement]),
                ]
            )

    with TAG_COUNTS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["art_movement", "tag", "count"])
        for movement in sorted(TARGET_MOVEMENTS):
            for tag, count in movement_tag_counts[movement].most_common():
                writer.writerow([movement, tag, count])

    print(f"Filtered data saved to: {FILTERED_DATA_PATH.name}")
    print(f"Movement summary saved to: {MOVEMENT_COUNTS_PATH.name}")
    print(f"Tag counts saved to: {TAG_COUNTS_PATH.name}")
    print()
    print("Counts in filtered subset:")
    for movement in sorted(TARGET_MOVEMENTS):
        print(
            f"{movement}: {movement_counts[movement]} paintings, "
            f"{len(movement_tag_counts[movement])} unique tags"
        )


if __name__ == "__main__":
    main()
