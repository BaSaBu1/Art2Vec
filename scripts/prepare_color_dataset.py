"""
Step 3: Download each painting's WikiArt image and extract dominant colors as 108-bin HSV percentages.
Usage: python scripts/prepare_color_dataset.py [--movement all|<Movement>]
Inputs: data_clean/color_analysis_dataset.tsv
Outputs (per movement): color/by_movement/<movement>/extraction/color_network_base.tsv + summary files
"""

from __future__ import annotations

import argparse
import csv
import io
import re
from collections import Counter
from pathlib import Path
from time import perf_counter

import numpy as np
import requests
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "data_clean" / "color_analysis_dataset.tsv"
OUTPUT_DIR = BASE_DIR / "color"
BY_MOVEMENT_DIR = OUTPUT_DIR / "by_movement"
BINS_PATH = OUTPUT_DIR / "color_bins_108_hsv.csv"

DROP_COLUMNS = {
    "Dimensions",
    "Series",
    "Teachers",
    "Friends and Co-workers",
    "Family and Relatives",
    "Pupils",
    "Influenced by",
    "Influenced on",
    "Art institution",
    "Location",
    "Original Title",
}

TARGET_MOVEMENTS = {
    "Northern Renaissance",
    "Baroque",
    "Romanticism",
    "Impressionism",
    "Cubism",
}

H_BINS = 12
S_BINS = 3
V_BINS = 3
BIN_COUNT = H_BINS * S_BINS * V_BINS


def slugify(value: str) -> str:
    """Convert a movement name like 'Northern Renaissance' to a folder-safe string like 'northern_renaissance'."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert red/green/blue integer values (0-255) to a hex color string like '#ff8040'."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hsv_bin_center_to_rgb(bin_id: int) -> tuple[int, int, int]:
    """Return the RGB center color of the given HSV bin index."""
    h_idx = bin_id // (S_BINS * V_BINS)
    rem = bin_id % (S_BINS * V_BINS)
    s_idx = rem // V_BINS
    v_idx = rem % V_BINS

    h_center = int(round(((h_idx + 0.5) / H_BINS) * 255))
    s_center = int(round(((s_idx + 0.5) / S_BINS) * 255))
    v_center = int(round(((v_idx + 0.5) / V_BINS) * 255))

    # Pillow handles the HSV→RGB conversion
    rgb = Image.fromarray(np.array([[[h_center, s_center, v_center]]], dtype=np.uint8), mode="HSV").convert("RGB")
    r, g, b = rgb.getpixel((0, 0))
    return int(r), int(g), int(b)


def write_bins_file(force: bool = False) -> None:
    """Write the lookup table mapping each of the 108 bin IDs to its representative hex color."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if BINS_PATH.exists() and not force:
        return
    with BINS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["bin_id", "h_bin", "s_bin", "v_bin", "hex"])
        for bin_id in range(BIN_COUNT):
            h_idx = bin_id // (S_BINS * V_BINS)
            rem = bin_id % (S_BINS * V_BINS)
            s_idx = rem // V_BINS
            v_idx = rem % V_BINS
            r, g, b = hsv_bin_center_to_rgb(bin_id)
            writer.writerow([bin_id, h_idx, s_idx, v_idx, rgb_to_hex(r, g, b)])


def hsv_to_bin_index(hsv_pixels: np.ndarray) -> np.ndarray:
    """Map an (N, 3) array of HSV pixels (0-255) to integer bin IDs in [0, 107]."""
    h = hsv_pixels[:, 0].astype(np.int32)
    s = hsv_pixels[:, 1].astype(np.int32)
    v = hsv_pixels[:, 2].astype(np.int32)

    # Map each channel into its bucket index using integer division
    h_idx = np.minimum((h * H_BINS) // 256, H_BINS - 1)
    s_idx = np.minimum((s * S_BINS) // 256, S_BINS - 1)
    v_idx = np.minimum((v * V_BINS) // 256, V_BINS - 1)

    # Combine the three indices into a single bin number (0 to 107)
    return h_idx * (S_BINS * V_BINS) + s_idx * V_BINS + v_idx


def extract_bin_colors(
    image_bytes: bytes,
    min_pct: float,
    max_side: int,
    min_keep_count: int,
) -> list[tuple[int, float]]:
    """Return (bin_id, fraction) pairs for the painting's dominant colors (≥ min_pct or top min_keep_count)."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        hsv = img.convert("HSV")
        if max(hsv.size) > max_side:
            hsv.thumbnail((max_side, max_side))   # resize large images to save time
        pixels = np.asarray(hsv, dtype=np.uint8).reshape(-1, 3)

    if pixels.shape[0] == 0:
        raise ValueError("Image has no pixels after conversion")

    bin_ids = hsv_to_bin_index(pixels)
    counts = np.bincount(bin_ids, minlength=BIN_COUNT).astype(np.float64)
    percentages = counts / counts.sum()

    items: list[tuple[int, float]] = []
    for idx in np.argsort(-percentages):   # iterate from most common to least
        pct = float(percentages[idx])
        if pct < min_pct:
            continue
        items.append((int(idx), pct))

    # Always keep at least min_keep_count bins so the network has enough color nodes.
    if len(items) < min_keep_count:
        top_idx = np.argsort(-percentages)[:min_keep_count]
        items = [(int(idx), float(percentages[idx])) for idx in top_idx]

    return items


def build_output_header(source_header: list[str]) -> list[str]:
    """Build the column list for the output file: original columns minus clutter, plus three color columns."""
    kept = [column for column in source_header if column not in DROP_COLUMNS]
    return kept + ["ColorTagsHex", "ColorTagsPct", "ColorBinIds"]


def prepare_for_movement(
    movement: str,
    timeout: int,
    min_pct: float,
    max_side: int,
    min_keep_count: int,
) -> None:
    start = perf_counter()
    movement_slug = slugify(movement)
    movement_dir = BY_MOVEMENT_DIR / movement_slug
    extraction_dir = movement_dir / "extraction"
    extraction_dir.mkdir(parents=True, exist_ok=True)

    output_path = extraction_dir / "color_network_base.tsv"
    failures_path = extraction_dir / "color_extraction_failures.csv"
    summary_path = extraction_dir / "color_prep_summary.csv"
    counts_path = extraction_dir / "color_tag_counts.csv"

    total_rows = 0
    processed_rows = 0
    failed_rows = 0
    color_occurrence: Counter[str] = Counter()

    with (
        INPUT_PATH.open(newline="", encoding="utf-8") as source,
        output_path.open("w", newline="", encoding="utf-8") as output,
        failures_path.open("w", newline="", encoding="utf-8") as failures,
    ):
        reader = csv.reader(source, delimiter="\t")
        source_header = next(reader)
        header_index = {name: idx for idx, name in enumerate(source_header)}

        movement_idx = header_index["Art Movement"]
        url_idx = header_index["image_url"]

        kept_columns = [column for column in source_header if column not in DROP_COLUMNS]
        kept_indices = [header_index[column] for column in kept_columns]

        writer = csv.writer(output, delimiter="\t")
        failure_writer = csv.writer(failures)

        writer.writerow(build_output_header(source_header))
        failure_writer.writerow(["art_movement", "painting_name", "image_url", "reason"])

        session = requests.Session()
        session.headers.update({"User-Agent": "Art2Vec-ColorPrep/1.0"})

        for row in reader:
            if len(row) <= max(movement_idx, url_idx):
                continue

            row_movement = row[movement_idx].strip()
            if row_movement != movement:
                continue

            total_rows += 1
            image_url = row[url_idx].strip()

            try:
                response = session.get(image_url, timeout=timeout)
                response.raise_for_status()
                color_items = extract_bin_colors(
                    response.content,
                    min_pct=min_pct,
                    max_side=max_side,
                    min_keep_count=min_keep_count,
                )
            except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
                failed_rows += 1
                painting_name = row[header_index.get("painting_name", 0)] if row else ""
                failure_writer.writerow([row_movement, painting_name, image_url, str(exc)])
                continue

            processed_rows += 1
            base_values = [row[idx] if idx < len(row) else "" for idx in kept_indices]

            color_hex_values = []
            color_bin_ids = []
            for bin_id, _ in color_items:
                r, g, b = hsv_bin_center_to_rgb(bin_id)
                color_hex_values.append(rgb_to_hex(r, g, b))
                color_bin_ids.append(str(bin_id))

            color_pct_values = [f"{pct:.4f}" for _, pct in color_items]

            for hex_value in set(color_hex_values):
                color_occurrence[hex_value] += 1

            writer.writerow(
                base_values
                + [
                    ",".join(color_hex_values),
                    ",".join(color_pct_values),
                    ",".join(color_bin_ids),
                ]
            )

    with counts_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["color_hex", "painting_count"])
        for color_hex, count in color_occurrence.most_common():
            writer.writerow([color_hex, count])

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
        success_rate = (processed_rows / total_rows) if total_rows else 0.0
        runtime_seconds = perf_counter() - start
        writer.writerow(
            [
                movement,
                total_rows,
                processed_rows,
                failed_rows,
                f"{success_rate:.4f}",
                f"{min_pct:.4f}",
                max_side,
                min_keep_count,
                f"{runtime_seconds:.2f}",
            ]
        )

    print(f"Movement: {movement}")
    print(f"Wrote: {output_path}")
    print(f"Wrote: {failures_path}")
    print(f"Wrote: {counts_path}")
    print(f"Wrote: {summary_path}")
    print(f"Input rows: {total_rows}")
    print(f"Processed rows: {processed_rows}")
    print(f"Failed rows: {failed_rows}")
    print(f"Runtime (seconds): {runtime_seconds:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare color-analysis base datasets with fixed HSV 108-bin extraction.")
    parser.add_argument(
        "--movement",
        default="Cubism",
        help="Art movement to process. Use 'all' to process the five selected movements.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds for image downloads.",
    )
    parser.add_argument(
        "--min-pct",
        type=float,
        default=0.04,
        help="Minimum color percentage to keep a color bin as part of a painting's color tags.",
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=1024,
        help="Max image side used before extraction.",
    )
    parser.add_argument(
        "--min-keep-count",
        type=int,
        default=3,
        help="Minimum number of color bins kept per painting.",
    )
    parser.add_argument(
        "--force-rebuild-bins",
        action="store_true",
        help="Rebuild color_bins_108_hsv.csv even if it already exists.",
    )
    args = parser.parse_args()

    write_bins_file(force=args.force_rebuild_bins)
    if args.force_rebuild_bins:
        print(f"Wrote: {BINS_PATH}")
    else:
        print(f"Using bins file: {BINS_PATH}")

    if args.movement.lower() == "all":
        for movement in sorted(TARGET_MOVEMENTS):
            prepare_for_movement(
                movement,
                timeout=args.timeout,
                min_pct=args.min_pct,
                max_side=args.max_side,
                min_keep_count=args.min_keep_count,
            )
    else:
        prepare_for_movement(
            args.movement,
            timeout=args.timeout,
            min_pct=args.min_pct,
            max_side=args.max_side,
            min_keep_count=args.min_keep_count,
        )


if __name__ == "__main__":
    main()
