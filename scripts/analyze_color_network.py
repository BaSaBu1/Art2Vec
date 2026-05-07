"""
This script builds color networks from the extracted HSV color bins. For each
movement, it keeps colors that appear often enough, connects paintings to their
retained colors, and then projects those links into a color co-occurrence
network. It writes the filtered color tables, edge lists, centrality measures,
graph summaries, and Gephi-ready exports used to study shared and distinctive
palettes.
"""

from __future__ import annotations

import argparse
import csv
import itertools
from collections import Counter
from pathlib import Path

import networkx as nx

BASE_DIR = Path(__file__).resolve().parents[1]
COLOR_BY_MOVEMENT_DIR = BASE_DIR / "color" / "by_movement"
SUMMARY_PATH = BASE_DIR / "color" / "color_network_summary.csv"


def hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
    value = hex_value.strip().lower().lstrip("#")
    if len(value) != 6:
        return 128, 128, 128
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def safe_round(value: float | None, digits: int = 6) -> float | str:
    if value is None:
        return "NA"
    return round(value, digits)


def projected_graph_stats(graph: nx.Graph) -> dict[str, float | int | str]:
    n = graph.number_of_nodes()
    m = graph.number_of_edges()
    component_count = nx.number_connected_components(graph) if n > 0 else 0

    if n > 0 and component_count > 0:
        giant_nodes = max(nx.connected_components(graph), key=len)
        giant = graph.subgraph(giant_nodes).copy()
        giant_n = giant.number_of_nodes()
        giant_m = giant.number_of_edges()
    else:
        giant = nx.Graph()
        giant_n = 0
        giant_m = 0

    avg_degree = (2 * m / n) if n > 0 else 0.0
    avg_weighted_degree = sum(dict(graph.degree(weight="weight")).values()) / n if n > 0 else 0.0

    avg_shortest_path = None
    diameter = None
    if giant_n > 1 and nx.is_connected(giant):
        avg_shortest_path = nx.average_shortest_path_length(giant)
        diameter = nx.diameter(giant)

    return {
        "nodes": n,
        "edges": m,
        "density": safe_round(nx.density(graph) if n > 1 else 0.0),
        "components": component_count,
        "giant_component_nodes": giant_n,
        "giant_component_edges": giant_m,
        "avg_degree": safe_round(avg_degree),
        "avg_weighted_degree": safe_round(avg_weighted_degree),
        "average_clustering": safe_round(nx.average_clustering(graph, weight="weight") if n > 1 else 0.0),
        "transitivity": safe_round(nx.transitivity(graph) if n > 2 else 0.0),
        "average_shortest_path_giant": safe_round(avg_shortest_path),
        "diameter_giant": diameter if diameter is not None else "NA",
    }


def parse_colors_and_pcts(row: dict[str, str]) -> list[tuple[str, float]]:
    colors = [c.strip().lower() for c in (row.get("ColorTagsHex") or "").split(",") if c.strip()]
    pcts_raw = [p.strip() for p in (row.get("ColorTagsPct") or "").split(",") if p.strip()]

    items: list[tuple[str, float]] = []
    for color, pct in zip(colors, pcts_raw):
        try:
            items.append((color, float(pct)))
        except ValueError:
            continue
    return items


def determine_threshold(paintings: int, floor: int, rate: float, override: int | None) -> int:
    if override is not None:
        return max(1, override)
    return max(floor, round(rate * paintings))


def build_for_movement(
    movement_dir: Path,
    min_occurrence_override: int | None,
    occurrence_floor: int,
    occurrence_rate: float,
) -> dict[str, int | float | str]:
    movement = movement_dir.name.replace("_", " ").title()
    extraction_dir = movement_dir / "extraction"
    network_dir = movement_dir / "network"
    network_dir.mkdir(parents=True, exist_ok=True)

    input_path = extraction_dir / "color_network_base.tsv"
    if not input_path.exists():
        raise FileNotFoundError(f"Missing input dataset: {input_path}")

    rows: list[dict[str, str]] = []
    with input_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            rows.append(row)

    paintings_before = len(rows)

    color_occurrence: Counter[str] = Counter()
    for row in rows:
        colors = {color for color, _ in parse_colors_and_pcts(row)}
        color_occurrence.update(colors)

    colors_before = len(color_occurrence)
    threshold = determine_threshold(
        paintings=paintings_before,
        floor=occurrence_floor,
        rate=occurrence_rate,
        override=min_occurrence_override,
    )

    # Rare bins are removed before projection so isolated colors do not create
    # noisy nodes with little interpretive value.
    kept_colors = {color for color, count in color_occurrence.items() if count >= threshold}

    filtered_rows: list[dict[str, str]] = []
    for row in rows:
        items = [(c, p) for c, p in parse_colors_and_pcts(row) if c in kept_colors]
        if not items:
            continue

        row = dict(row)
        row["ColorTagsHex"] = ",".join([c for c, _ in items])
        row["ColorTagsPct"] = ",".join([f"{p:.4f}" for _, p in items])
        filtered_rows.append(row)

    paintings_after = len(filtered_rows)

    thresholded_base_path = network_dir / "color_network_base_thresholded.tsv"
    if filtered_rows:
        fieldnames = list(filtered_rows[0].keys())
        with thresholded_base_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(filtered_rows)

    threshold_summary_path = network_dir / "color_threshold_summary.csv"
    with threshold_summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "movement",
                "paintings_before",
                "paintings_after",
                "colors_before",
                "colors_after",
                "min_occurrence",
                "occurrence_rate",
                "occurrence_floor",
            ]
        )
        writer.writerow(
            [
                movement,
                paintings_before,
                paintings_after,
                colors_before,
                len(kept_colors),
                threshold,
                f"{occurrence_rate:.4f}",
                occurrence_floor,
            ]
        )

    # Build bipartite graph with percentage as edge weight.
    bipartite_graph = nx.Graph()
    painting_colors_for_projection: dict[str, list[str]] = {}

    for row in filtered_rows:
        painting_id_source = (row.get("Path") or "").strip() or (row.get("painting_name") or "").strip()
        painting_label = (row.get("painting_name") or painting_id_source).strip()
        painting_id = f"painting::{painting_id_source}"

        items = parse_colors_and_pcts(row)
        if not items:
            continue

        bipartite_graph.add_node(painting_id, node_type="painting", label=painting_label)

        unique_colors: list[str] = []
        seen = set()
        for color_hex, pct in items:
            color_id = f"color::{color_hex}"
            bipartite_graph.add_node(color_id, node_type="color", label=color_hex)
            bipartite_graph.add_edge(painting_id, color_id, weight=pct)
            if color_hex not in seen:
                unique_colors.append(color_hex)
                seen.add(color_hex)

        painting_colors_for_projection[painting_id] = unique_colors

    # Projection: count paintings where both colors are present.
    projected = nx.Graph()
    for color_hex in kept_colors:
        color_id = f"color::{color_hex}"
        projected.add_node(color_id, label=color_hex)

    pair_counts: Counter[tuple[str, str]] = Counter()
    for colors in painting_colors_for_projection.values():
        for color_a, color_b in itertools.combinations(sorted(colors), 2):
            pair_counts[(color_a, color_b)] += 1

    for (color_a, color_b), count in pair_counts.items():
        projected.add_edge(f"color::{color_a}", f"color::{color_b}", weight=count)

    # Centralities summarize which colors sit at the center of the movement's
    # shared palette, even though the color-rank display became more useful for
    # the final website.
    degree_centrality = nx.degree_centrality(projected) if projected.number_of_nodes() > 1 else {}
    weighted_degree = dict(projected.degree(weight="weight"))
    betweenness = (
        nx.betweenness_centrality(projected, weight="weight", normalized=True)
        if projected.number_of_nodes() > 1
        else {}
    )
    closeness = (
        nx.closeness_centrality(projected, distance=None)
        if projected.number_of_nodes() > 1
        else {}
    )
    try:
        eigenvector = (
            nx.eigenvector_centrality_numpy(projected, weight="weight")
            if projected.number_of_nodes() > 1 and projected.number_of_edges() > 0
            else {}
        )
    except Exception:
        eigenvector = {}
    pagerank = (
        nx.pagerank(projected, weight="weight")
        if projected.number_of_nodes() > 1 and projected.number_of_edges() > 0
        else {}
    )

    # Outputs.
    nodes_path = network_dir / "color_painting_nodes.csv"
    bipartite_edges_path = network_dir / "color_painting_edges.csv"
    projected_edges_path = network_dir / "color_projected_edges.csv"
    centrality_path = network_dir / "color_centrality.csv"
    stats_path = network_dir / "color_graph_stats.csv"
    gephi_nodes_path = network_dir / "gephi_color_nodes.csv"
    gephi_edges_path = network_dir / "gephi_color_edges.csv"
    gephi_gexf_path = network_dir / "gephi_color_network.gexf"

    with nodes_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["node_id", "node_type", "label", "degree"])
        for node_id, attrs in bipartite_graph.nodes(data=True):
            writer.writerow([node_id, attrs.get("node_type", ""), attrs.get("label", ""), bipartite_graph.degree(node_id)])

    with bipartite_edges_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["painting_id", "color_hex", "weight"])
        for u, v, attrs in bipartite_graph.edges(data=True):
            painting_node = u if u.startswith("painting::") else v
            color_node = v if v.startswith("color::") else u
            writer.writerow([painting_node, bipartite_graph.nodes[color_node]["label"], f"{attrs.get('weight', 0):.6f}"])

    with projected_edges_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["color_a", "color_b", "shared_paintings"])
        for u, v, attrs in projected.edges(data=True):
            writer.writerow([projected.nodes[u]["label"], projected.nodes[v]["label"], attrs.get("weight", 0)])

    ranked_colors = sorted(
        [n for n, d in projected.nodes(data=True)],
        key=lambda node: (weighted_degree.get(node, 0), degree_centrality.get(node, 0.0), pagerank.get(node, 0.0)),
        reverse=True,
    )
    with centrality_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "color_hex",
                "degree_centrality",
                "weighted_degree",
                "betweenness_centrality",
                "closeness_centrality",
                "eigenvector_centrality",
                "pagerank",
            ]
        )
        for node in ranked_colors:
            writer.writerow(
                [
                    projected.nodes[node]["label"],
                    round(degree_centrality.get(node, 0.0), 6),
                    int(weighted_degree.get(node, 0)),
                    round(betweenness.get(node, 0.0), 6),
                    round(closeness.get(node, 0.0), 6),
                    round(eigenvector.get(node, 0.0), 6),
                    round(pagerank.get(node, 0.0), 6),
                ]
            )

    stats = projected_graph_stats(projected)
    with stats_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "movement",
                "nodes",
                "edges",
                "density",
                "components",
                "giant_component_nodes",
                "giant_component_edges",
                "avg_degree",
                "avg_weighted_degree",
                "average_clustering",
                "transitivity",
                "average_shortest_path_giant",
                "diameter_giant",
            ]
        )
        writer.writerow(
            [
                movement,
                stats["nodes"],
                stats["edges"],
                stats["density"],
                stats["components"],
                stats["giant_component_nodes"],
                stats["giant_component_edges"],
                stats["avg_degree"],
                stats["avg_weighted_degree"],
                stats["average_clustering"],
                stats["transitivity"],
                stats["average_shortest_path_giant"],
                stats["diameter_giant"],
            ]
        )

    with gephi_nodes_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "label", "hex", "r", "g", "b"])
        for node_id, attrs in projected.nodes(data=True):
            color_hex = attrs.get("label", "")
            r, g, b = hex_to_rgb(color_hex)
            writer.writerow([color_hex, color_hex, color_hex, r, g, b])

    with gephi_edges_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["source", "target", "weight"])
        for u, v, attrs in projected.edges(data=True):
            writer.writerow([projected.nodes[u]["label"], projected.nodes[v]["label"], attrs.get("weight", 0)])

    gephi_graph = nx.Graph()
    for node_id, attrs in projected.nodes(data=True):
        color_hex = attrs.get("label", "")
        r, g, b = hex_to_rgb(color_hex)
        gephi_graph.add_node(
            color_hex,
            label=color_hex,
            viz={"color": {"r": r, "g": g, "b": b, "a": 1.0}},
        )

    for u, v, attrs in projected.edges(data=True):
        source = projected.nodes[u]["label"]
        target = projected.nodes[v]["label"]
        gephi_graph.add_edge(source, target, weight=attrs.get("weight", 0))

    nx.write_gexf(gephi_graph, gephi_gexf_path)

    print(f"Movement: {movement}")
    print(f"Wrote: {thresholded_base_path}")
    print(f"Wrote: {threshold_summary_path}")
    print(f"Wrote: {nodes_path}")
    print(f"Wrote: {bipartite_edges_path}")
    print(f"Wrote: {projected_edges_path}")
    print(f"Wrote: {centrality_path}")
    print(f"Wrote: {stats_path}")
    print(f"Wrote: {gephi_nodes_path}")
    print(f"Wrote: {gephi_edges_path}")
    print(f"Wrote: {gephi_gexf_path}")

    return {
        "movement": movement,
        "paintings_before": paintings_before,
        "paintings_after": paintings_after,
        "colors_before": colors_before,
        "colors_after": len(kept_colors),
        "min_occurrence": threshold,
        "painting_nodes": len([n for n, d in bipartite_graph.nodes(data=True) if d.get("node_type") == "painting"]),
        "color_nodes": len([n for n, d in bipartite_graph.nodes(data=True) if d.get("node_type") == "color"]),
        "bipartite_edges": bipartite_graph.number_of_edges(),
        "projected_edges": projected.number_of_edges(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build color networks and centralities from extracted color tags.")
    parser.add_argument(
        "--movement",
        default="all",
        help="Movement folder slug under color/by_movement, or 'all'.",
    )
    parser.add_argument(
        "--min-occurrence",
        type=int,
        default=None,
        help="Absolute minimum painting occurrence for colors. If omitted, dynamic threshold is used.",
    )
    parser.add_argument(
        "--occurrence-floor",
        type=int,
        default=8,
        help="Dynamic threshold floor when --min-occurrence is not provided.",
    )
    parser.add_argument(
        "--occurrence-rate",
        type=float,
        default=0.005,
        help="Dynamic threshold rate when --min-occurrence is not provided.",
    )
    args = parser.parse_args()

    if args.movement.lower() == "all":
        movement_dirs = sorted([d for d in COLOR_BY_MOVEMENT_DIR.iterdir() if d.is_dir()])
    else:
        movement_dirs = [COLOR_BY_MOVEMENT_DIR / args.movement]

    summaries: list[dict[str, int | float | str]] = []
    for movement_dir in movement_dirs:
        summaries.append(
            build_for_movement(
                movement_dir=movement_dir,
                min_occurrence_override=args.min_occurrence,
                occurrence_floor=args.occurrence_floor,
                occurrence_rate=args.occurrence_rate,
            )
        )

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "movement",
                "paintings_before",
                "paintings_after",
                "colors_before",
                "colors_after",
                "min_occurrence",
                "painting_nodes",
                "color_nodes",
                "bipartite_edges",
                "projected_edges",
            ]
        )
        for row in summaries:
            writer.writerow(
                [
                    row["movement"],
                    row["paintings_before"],
                    row["paintings_after"],
                    row["colors_before"],
                    row["colors_after"],
                    row["min_occurrence"],
                    row["painting_nodes"],
                    row["color_nodes"],
                    row["bipartite_edges"],
                    row["projected_edges"],
                ]
            )

    print(f"Wrote: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
