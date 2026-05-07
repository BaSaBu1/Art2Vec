"""
This script compares the extracted color profiles across the five movements.
It ranks the most common colors within each movement, measures how similar the
movement palettes are to one another, identifies colors that are unusually
important to a movement compared with the full collection, and summarizes how
much the top palettes overlap.
"""

from __future__ import annotations

import csv
import itertools
import math
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
COLOR_BASE = BASE_DIR / "color" / "by_movement"
OUT_DIR = Path(__file__).resolve().parents[1] / "results"


def load_movement_counts() -> dict[str, Counter[str]]:
    """Load each movement's color frequency data from the color_tag_counts.csv files produced in Phase 1."""
    movement_counts: dict[str, Counter[str]] = {}
    for movement_dir in sorted([d for d in COLOR_BASE.iterdir() if d.is_dir()]):
        counts_path = movement_dir / "extraction" / "color_tag_counts.csv"
        if not counts_path.exists():
            continue

        counts: Counter[str] = Counter()
        with counts_path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                color_hex = (row.get("color_hex") or "").strip().lower()
                if not color_hex:
                    continue
                counts[color_hex] = int(row.get("painting_count") or 0)

        movement_counts[movement_dir.name] = counts

    return movement_counts


def cosine_similarity(a: Counter[str], b: Counter[str], universe: list[str]) -> float:
    """Cosine similarity between two color-count vectors over the given universe of colors."""
    dot = sum(a.get(c, 0) * b.get(c, 0) for c in universe)
    na = math.sqrt(sum((a.get(c, 0) ** 2) for c in universe))
    nb = math.sqrt(sum((b.get(c, 0) ** 2) for c in universe))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def top_n(counter: Counter[str], n: int) -> list[str]:
    return [color for color, _ in counter.most_common(n)]


def write_core_colors(movement_counts: dict[str, Counter[str]], n: int = 20) -> Path:
    output_path = OUT_DIR / "core_colors_top20.csv"
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["movement", "rank", "color_hex", "painting_count"])
        for movement in sorted(movement_counts):
            for rank, (color, count) in enumerate(movement_counts[movement].most_common(n), start=1):
                writer.writerow([movement, rank, color, count])
    return output_path


def write_pairwise_similarity(movement_counts: dict[str, Counter[str]]) -> Path:
    output_path = OUT_DIR / "pairwise_color_similarity.csv"
    movements = sorted(movement_counts)
    universe = sorted(set().union(*[set(movement_counts[m].keys()) for m in movements]))

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["movement_a", "movement_b", "cosine_counts", "jaccard_top20"])
        for a, b in itertools.combinations(movements, 2):
            cos = cosine_similarity(movement_counts[a], movement_counts[b], universe)
            top_a = set(top_n(movement_counts[a], 20))
            top_b = set(top_n(movement_counts[b], 20))
            union = top_a | top_b
            jaccard = (len(top_a & top_b) / len(union)) if union else 0.0
            writer.writerow([a, b, f"{cos:.6f}", f"{jaccard:.6f}"])

    return output_path


def write_distinctive_colors(movement_counts: dict[str, Counter[str]], support_min: int = 20, top_k: int = 20) -> Path:
    output_path = OUT_DIR / "distinctive_colors_lift.csv"

    # Lift compares a color's share inside one movement against its share in
    # the full corpus, which highlights accents rather than just common colors.
    global_counts: Counter[str] = Counter()
    for movement in movement_counts:
        global_counts.update(movement_counts[movement])

    global_total = sum(global_counts.values())

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "movement",
                "rank",
                "color_hex",
                "painting_count",
                "movement_share",
                "global_share",
                "lift",
            ]
        )

        for movement in sorted(movement_counts):
            counts = movement_counts[movement]
            movement_total = sum(counts.values())
            rows: list[tuple[float, str, int, float, float]] = []

            for color_hex, count in counts.items():
                if count < support_min:
                    continue
                movement_share = count / movement_total if movement_total else 0.0
                global_share = global_counts[color_hex] / global_total if global_total else 0.0
                lift = (movement_share / global_share) if global_share else 0.0
                rows.append((lift, color_hex, count, movement_share, global_share))

            rows.sort(reverse=True)
            for rank, (lift, color_hex, count, ms, gs) in enumerate(rows[:top_k], start=1):
                writer.writerow([movement, rank, color_hex, count, f"{ms:.6f}", f"{gs:.6f}", f"{lift:.6f}"])

    return output_path


def write_shared_vs_unique(movement_counts: dict[str, Counter[str]], n: int = 20) -> Path:
    output_path = OUT_DIR / "shared_vs_unique_top20.csv"
    movements = sorted(movement_counts)

    # This overlap check explains why a color network alone was not very
    # distinctive: most top colors are shared across movements.
    top_by_movement = {m: top_n(movement_counts[m], n) for m in movements}
    frequency = Counter()
    for m in movements:
        frequency.update(top_by_movement[m])

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["movement", "shared_top20_count", "unique_top20_count", "example_unique_hex"])

        for m in movements:
            top_colors = top_by_movement[m]
            shared_count = sum(1 for c in top_colors if frequency[c] > 1)
            unique = [c for c in top_colors if frequency[c] == 1]
            example_unique = unique[0] if unique else "(none)"
            writer.writerow([m, shared_count, len(unique), example_unique])

    return output_path


def write_readme(outputs: list[Path]) -> Path:
    output_path = OUT_DIR / "README_color_analysis.md"
    with output_path.open("w", encoding="utf-8") as file:
        file.write("# Color Movement-Distinction Analysis\n\n")
        file.write("Generated outputs:\n")
        for p in outputs:
            file.write(f"- {p.name}\n")
        file.write("\n")
        file.write("## Notes\n")
        file.write("- `core_colors_top20.csv`: most frequent colors per movement.\n")
        file.write("- `pairwise_color_similarity.csv`: movement similarity by cosine and top-20 Jaccard.\n")
        file.write("- `distinctive_colors_lift.csv`: movement-specific colors by lift against global baseline.\n")
        file.write("- `shared_vs_unique_top20.csv`: top-20 overlap diagnostic per movement.\n")
    return output_path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    movement_counts = load_movement_counts()
    if not movement_counts:
        raise RuntimeError("No movement color count files found under color/by_movement/*/extraction")

    outputs = [
        write_core_colors(movement_counts),
        write_pairwise_similarity(movement_counts),
        write_distinctive_colors(movement_counts),
        write_shared_vs_unique(movement_counts),
    ]
    outputs.append(write_readme(outputs))

    for output in outputs:
        print(f"Wrote: {output}")


if __name__ == "__main__":
    main()
