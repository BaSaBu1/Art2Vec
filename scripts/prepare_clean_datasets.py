"""
This script turns the filtered five-movement data into two cleaner analysis
tables. The color table keeps every retained painting because color extraction
can still work when a motif is rare, while the motif table keeps only motifs
that passed the frequency threshold so the motif networks are not dominated by
one-off tags. It also writes a compact summary showing how many paintings remain
in each version of the cleaned data.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "raw_data_eda"
CLEAN_DIR = BASE_DIR / "data_clean"

SOURCE_DATASET = RAW_DIR / "filtered_5movements_with_tags.tsv"
THRESHOLDED_TAGS = RAW_DIR / "filtered_5movements_tag_counts_thresholded.csv"

MOTIF_OUTPUT = CLEAN_DIR / "motif_analysis_dataset.tsv"
COLOR_OUTPUT = CLEAN_DIR / "color_analysis_dataset.tsv"
SUMMARY_OUTPUT = CLEAN_DIR / "clean_dataset_summary.csv"


def split_tags(tag_value: str) -> list[str]:
    """Split a tag string into individual tag names."""
    return [part.strip() for part in re.split(r"[;,|]", tag_value or "") if part.strip()]


def load_kept_tags() -> dict[str, set[str]]:
    """Return a dict mapping each movement to the tags that passed the frequency threshold."""
    kept: defaultdict[str, set[str]] = defaultdict(set)
    with THRESHOLDED_TAGS.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            kept[row["art_movement"]].add(row["tag"])
    return dict(kept)


def main() -> None:
    if not SOURCE_DATASET.exists():
        raise FileNotFoundError(f"Missing source dataset: {SOURCE_DATASET}")
    if not THRESHOLDED_TAGS.exists():
        raise FileNotFoundError(f"Missing thresholded tags file: {THRESHOLDED_TAGS}")

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    kept_tags = load_kept_tags()

    color_rows = 0
    motif_rows = 0
    movement_color_counts: Counter[str] = Counter()
    movement_motif_counts: Counter[str] = Counter()

    with (
        SOURCE_DATASET.open(newline="", encoding="utf-8") as source,
        COLOR_OUTPUT.open("w", newline="", encoding="utf-8") as color_out,
        MOTIF_OUTPUT.open("w", newline="", encoding="utf-8") as motif_out,
    ):
        reader = csv.reader(source, delimiter="\t")
        color_writer = csv.writer(color_out, delimiter="\t")
        motif_writer = csv.writer(motif_out, delimiter="\t")

        header = next(reader)
        color_writer.writerow(header)
        motif_writer.writerow(header)

        movement_idx = header.index("Art Movement")
        tag_idx = header.index("Tag") if "Tag" in header else header.index("tags")

        for row in reader:
            if len(row) <= max(movement_idx, tag_idx):
                continue

            movement = row[movement_idx].strip()
            tag_value = row[tag_idx].strip()

            # Color analysis needs all available paintings, so the row is
            # written before any motif threshold is applied.
            color_writer.writerow(row)
            color_rows += 1
            movement_color_counts[movement] += 1

            retained = [tag for tag in split_tags(tag_value) if tag in kept_tags.get(movement, set())]
            if not retained:
                continue

            # Motif analysis uses the same metadata row but replaces the raw
            # tag string with only the retained motif vocabulary.
            new_row = list(row)
            new_row[tag_idx] = ";".join(retained)
            motif_writer.writerow(new_row)
            motif_rows += 1
            movement_motif_counts[movement] += 1

    with SUMMARY_OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "art_movement",
            "color_dataset_rows",
            "motif_dataset_rows",
            "removed_for_motif",
        ])
        movements = sorted(set(movement_color_counts) | set(movement_motif_counts))
        for movement in movements:
            color_count = movement_color_counts[movement]
            motif_count = movement_motif_counts[movement]
            writer.writerow([
                movement,
                color_count,
                motif_count,
                color_count - motif_count,
            ])

    print(f"Wrote: {COLOR_OUTPUT}")
    print(f"Wrote: {MOTIF_OUTPUT}")
    print(f"Wrote: {SUMMARY_OUTPUT}")
    print(f"Color dataset rows: {color_rows}")
    print(f"Motif dataset rows: {motif_rows}")


if __name__ == "__main__":
    main()
