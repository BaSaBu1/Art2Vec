"""
Step 0: Count paintings and tag frequencies per movement in the raw ART500K dataset.
Requires raw data (not included in submission); outputs saved to raw_data_eda/.
Inputs: data/label_list.tsv, data/head_info.csv
Outputs: data/art_movement_tagged_counts.csv, data/top10_art_movement_tags.csv
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
MOVEMENT_SUMMARY_PATH = DATA_DIR / "art_movement_tagged_counts.csv"
TOP_TAGS_PATH = DATA_DIR / "top10_art_movement_tags.csv"


def split_tags(tag_value: str) -> list[str]:
    """Split a raw tag string into individual tag names, handling multiple separators."""
    parts = [part.strip() for part in re.split(r"[;,|]", tag_value) if part.strip()]
    return parts if parts else []


def load_columns() -> list[str]:
    """Read the column names for the ART500K metadata file from head_info.csv."""
    with HEAD_INFO_PATH.open(encoding="utf-8") as file:
        raw = file.read().strip()

    return list(ast.literal_eval(raw))


def main() -> None:
    columns = load_columns()
    art_movement_idx = columns.index("Art Movement")
    tag_idx = columns.index("Tag") if "Tag" in columns else columns.index("tags")

    movement_tagged_counts = Counter()
    movement_tag_counts = defaultdict(Counter)
    tagged_rows = 0
    total_rows = 0

    with LABEL_LIST_PATH.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            if len(row) <= max(art_movement_idx, tag_idx):
                continue

            total_rows += 1
            movement = row[art_movement_idx].strip()
            tag = row[tag_idx].strip()

            if movement and tag:
                movement_tagged_counts[movement] += 1
                tagged_rows += 1
                for tag_value in split_tags(tag):
                    movement_tag_counts[movement][tag_value] += 1

    top_movements = [movement for movement, _ in movement_tagged_counts.most_common(10)]

    with MOVEMENT_SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["art_movement", "tagged_paintings", "unique_tags"])
        for movement, count in movement_tagged_counts.most_common():
            writer.writerow([movement, count, len(movement_tag_counts[movement])])

    with TOP_TAGS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["art_movement", "tag", "count"])
        for movement in top_movements:
            for tag, count in movement_tag_counts[movement].most_common():
                writer.writerow([movement, tag, count])

    print(f"Total rows: {total_rows}")
    print(f"Rows with a non-empty tag: {tagged_rows}")
    print()
    print(f"Saved movement summary to: {MOVEMENT_SUMMARY_PATH.name}")
    print(f"Saved top-10 tag breakdown to: {TOP_TAGS_PATH.name}")
    print()
    print("Top 10 art movements with tags:")
    for movement, count in movement_tagged_counts.most_common(10):
        print(f"{movement}\t{count}")


if __name__ == "__main__":
    main()
