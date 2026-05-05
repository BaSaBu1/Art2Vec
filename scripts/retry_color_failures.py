"""
Recovery: re-attempt rows that failed in prepare_color_dataset.py and patch the output files in place.
Usage: python scripts/retry_color_failures.py [--movement Romanticism]
Inputs/Outputs: color/by_movement/<movement>/extraction/ (patches color_network_base.tsv and related files)
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from time import perf_counter

import requests
from PIL import UnidentifiedImageError

import prepare_color_dataset as color_prep

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "data_clean" / "color_analysis_dataset.tsv"
COLOR_DIR = BASE_DIR / "color" / "by_movement"


def load_source_rows(movement: str) -> tuple[list[str], dict[str, list[str]]]:
    """Load the original metadata rows for a given movement, indexed by image URL for fast lookup."""
    with INPUT_PATH.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter="\t")
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}
        movement_idx = idx["Art Movement"]
        url_idx = idx["image_url"]

        rows: dict[str, list[str]] = {}
        for row in reader:
            if len(row) <= max(movement_idx, url_idx):
                continue
            if row[movement_idx].strip() != movement:
                continue
            rows[row[url_idx].strip()] = row
        return header, rows


def retry_movement(movement: str, timeout: int, min_pct: float, max_side: int, min_keep_count: int) -> None:
    movement_slug = color_prep.slugify(movement)
    movement_dir = COLOR_DIR / movement_slug
    extraction_dir = movement_dir / "extraction"

    base_path = extraction_dir / "color_network_base.tsv"
    failures_path = extraction_dir / "color_extraction_failures.csv"
    summary_path = extraction_dir / "color_prep_summary.csv"
    counts_path = extraction_dir / "color_tag_counts.csv"

    if not failures_path.exists():
        raise FileNotFoundError(f"Missing failures file: {failures_path}")

    with failures_path.open(newline="", encoding="utf-8") as file:
        failure_reader = csv.DictReader(file)
        failed_rows = list(failure_reader)

    if not failed_rows:
        print(f"No failed rows to retry for {movement}.")
        return

    source_header, source_by_url = load_source_rows(movement)
    source_idx = {name: i for i, name in enumerate(source_header)}

    kept_columns = [column for column in source_header if column not in color_prep.DROP_COLUMNS]
    kept_indices = [source_idx[column] for column in kept_columns]

    existing_urls: set[str] = set()
    with base_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            existing_urls.add((row.get("image_url") or "").strip())

    retry_start = perf_counter()
    retried_success = 0
    still_failed: list[dict[str, str]] = []

    session = requests.Session()
    session.headers.update({"User-Agent": "Art2Vec-ColorPrep-Retry/1.0"})

    with base_path.open("a", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, delimiter="\t")

        for failure in failed_rows:
            image_url = (failure.get("image_url") or "").strip()
            if not image_url:
                continue
            if image_url in existing_urls:
                continue

            row = source_by_url.get(image_url)
            if row is None:
                failure["reason"] = "Source row not found in color_analysis_dataset.tsv"
                still_failed.append(failure)
                continue

            try:
                response = session.get(image_url, timeout=timeout)
                response.raise_for_status()
                color_items = color_prep.extract_bin_colors(
                    response.content,
                    min_pct=min_pct,
                    max_side=max_side,
                    min_keep_count=min_keep_count,
                )
            except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
                failure["reason"] = str(exc)
                still_failed.append(failure)
                continue

            base_values = [row[idx] if idx < len(row) else "" for idx in kept_indices]
            color_hex_values = []
            color_bin_ids = []
            for bin_id, _ in color_items:
                r, g, b = color_prep.hsv_bin_center_to_rgb(bin_id)
                color_hex_values.append(color_prep.rgb_to_hex(r, g, b))
                color_bin_ids.append(str(bin_id))
            color_pct_values = [f"{pct:.4f}" for _, pct in color_items]

            writer.writerow(base_values + [",".join(color_hex_values), ",".join(color_pct_values), ",".join(color_bin_ids)])
            existing_urls.add(image_url)
            retried_success += 1

    # Rewrite failures file with remaining failures only.
    with failures_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["art_movement", "painting_name", "image_url", "reason"])
        for row in still_failed:
            writer.writerow([
                row.get("art_movement", movement),
                row.get("painting_name", ""),
                row.get("image_url", ""),
                row.get("reason", ""),
            ])

    # Rebuild color_tag_counts from current base file.
    color_occurrence: Counter[str] = Counter()
    total_rows = 0
    with base_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            total_rows += 1
            for hex_value in (row.get("ColorTagsHex") or "").split(","):
                hex_value = hex_value.strip()
                if hex_value:
                    color_occurrence[hex_value] += 1

    with counts_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["color_hex", "painting_count"])
        for color_hex, count in color_occurrence.most_common():
            writer.writerow([color_hex, count])

    # Update summary while preserving prior runtime in cumulative form.
    prior_runtime = 0.0
    input_rows = total_rows
    with summary_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
        if rows:
            input_rows = int(rows[0].get("input_rows", total_rows) or total_rows)
            try:
                prior_runtime = float(rows[0].get("runtime_seconds", "0") or 0.0)
            except ValueError:
                prior_runtime = 0.0

    remaining_failures = len(still_failed)
    processed_rows = total_rows
    success_rate = processed_rows / input_rows if input_rows else 0.0
    retry_runtime = perf_counter() - retry_start

    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "art_movement",
                "input_rows",
                "processed_rows",
                "failed_rows",
                "success_rate",
                "min_color_pct",
                "max_image_side",
                "min_keep_count",
                "runtime_seconds",
            ]
        )
        writer.writerow(
            [
                movement,
                input_rows,
                processed_rows,
                remaining_failures,
                f"{success_rate:.4f}",
                f"{min_pct:.4f}",
                max_side,
                min_keep_count,
                f"{prior_runtime + retry_runtime:.2f}",
            ]
        )

    print(f"Movement: {movement}")
    print(f"Retried rows: {len(failed_rows)}")
    print(f"Recovered rows: {retried_success}")
    print(f"Remaining failures: {remaining_failures}")
    print(f"Retry runtime (seconds): {retry_runtime:.2f}")
    print(f"Updated: {base_path}")
    print(f"Updated: {failures_path}")
    print(f"Updated: {counts_path}")
    print(f"Updated: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed color extraction rows only.")
    parser.add_argument("--movement", default="Romanticism")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--min-pct", type=float, default=0.04)
    parser.add_argument("--max-side", type=int, default=1024)
    parser.add_argument("--min-keep-count", type=int, default=3)
    args = parser.parse_args()

    retry_movement(
        movement=args.movement,
        timeout=args.timeout,
        min_pct=args.min_pct,
        max_side=args.max_side,
        min_keep_count=args.min_keep_count,
    )


if __name__ == "__main__":
    main()
