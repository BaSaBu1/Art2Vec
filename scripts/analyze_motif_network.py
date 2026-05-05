"""
Phase 1: Build painting-motif bipartite networks, project to motif co-occurrence graphs, and compute centrality.
Inputs: data_clean/motif_analysis_dataset.tsv
Outputs (per movement): motif/by_movement/<movement>/ — edges, centrality, graph stats, Gephi files
Also writes: motif/motif_network_summary.csv
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

import networkx as nx
from networkx.algorithms import bipartite

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = BASE_DIR / "data_clean" / "motif_analysis_dataset.tsv"
OUTPUT_DIR = BASE_DIR / "motif"
BY_MOVEMENT_DIR = OUTPUT_DIR / "by_movement"

SUMMARY_PATH = OUTPUT_DIR / "motif_network_summary.csv"


def split_tags(tag_value: str) -> list[str]:
    """Split a semicolon/comma-separated tag string into a list of individual tags."""
    return [part.strip() for part in re.split(r"[;,|]", tag_value or "") if part.strip()]


def movement_slug(name: str) -> str:
    """Convert a movement name to a filesystem-safe folder name (e.g. 'Northern Renaissance' → 'northern_renaissance')."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build_painting_id(row: list[str], header_index: dict[str, int]) -> tuple[str, str]:
    """Return (unique_id, label) for a painting, using Path or author|title as fallback."""
    path_idx = header_index.get("Path")
    author_idx = header_index.get("author_name")
    painting_idx = header_index.get("painting_name")

    path_value = row[path_idx].strip() if path_idx is not None and path_idx < len(row) else ""
    author_value = row[author_idx].strip() if author_idx is not None and author_idx < len(row) else ""
    painting_value = row[painting_idx].strip() if painting_idx is not None and painting_idx < len(row) else ""

    if path_value:
        return f"painting::{path_value}", painting_value or path_value

    # Fall back to "Author | Painting Name" if no file path is available
    composite = f"{author_value} | {painting_value}".strip(" |")
    return f"painting::{composite}", painting_value or composite


def safe_round(value: float | None, digits: int = 6) -> float | str:
    """Round a number to the given number of decimal places, or return 'NA' if the value is missing."""
    if value is None:
        return "NA"
    return round(value, digits)


def projected_graph_stats(graph: nx.Graph) -> dict[str, float | int | str]:
    """Return size, density, component count, and giant-component stats for the motif-motif graph."""
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
    avg_weighted_degree = (
        sum(dict(graph.degree(weight="weight")).values()) / n if n > 0 else 0.0
    )

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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BY_MOVEMENT_DIR.mkdir(parents=True, exist_ok=True)

    with INPUT_PATH.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter="\t")
        header = next(reader)

        header_index = {name: idx for idx, name in enumerate(header)}
        movement_idx = header_index["Art Movement"]
        tag_idx = header_index["Tag"] if "Tag" in header_index else header_index["tags"]

        movement_graphs: dict[str, nx.Graph] = defaultdict(nx.Graph)

        for row in reader:
            if len(row) <= max(movement_idx, tag_idx):
                continue

            movement = row[movement_idx].strip()
            tags = list(dict.fromkeys(split_tags(row[tag_idx].strip())))
            if not movement or not tags:
                continue

            painting_id, painting_label = build_painting_id(row, header_index)
            graph = movement_graphs[movement]

            graph.add_node(
                painting_id,
                bipartite="painting",
                node_type="painting",
                label=painting_label,
            )

            for tag in tags:
                motif_id = f"motif::{tag}"
                graph.add_node(
                    motif_id,
                    bipartite="motif",
                    node_type="motif",
                    label=tag,
                )
                graph.add_edge(painting_id, motif_id, weight=1)

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as summary_file:
        summary_writer = csv.writer(summary_file)

        summary_writer.writerow(
            [
                "art_movement",
                "painting_nodes",
                "motif_nodes",
                "bipartite_edges",
                "projected_motif_edges",
            ]
        )

        for movement in sorted(movement_graphs):
            graph = movement_graphs[movement]
            painting_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "painting"]
            motif_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "motif"]
            projected = bipartite.weighted_projected_graph(graph, motif_nodes)

            movement_dir = BY_MOVEMENT_DIR / movement_slug(movement)
            movement_dir.mkdir(parents=True, exist_ok=True)
            movement_nodes_path = movement_dir / "motif_painting_nodes.csv"
            movement_edges_path = movement_dir / "motif_painting_edges.csv"
            movement_projected_path = movement_dir / "motif_projected_edges.csv"
            movement_centrality_path = movement_dir / "motif_centrality.csv"
            movement_stats_path = movement_dir / "motif_graph_stats.csv"
            movement_gephi_nodes_path = movement_dir / "gephi_motif_nodes.csv"
            movement_gephi_edges_path = movement_dir / "gephi_motif_edges.csv"

            with (
                movement_nodes_path.open("w", newline="", encoding="utf-8") as movement_nodes_file,
                movement_edges_path.open("w", newline="", encoding="utf-8") as movement_edges_file,
                movement_projected_path.open("w", newline="", encoding="utf-8") as movement_projected_file,
                movement_centrality_path.open("w", newline="", encoding="utf-8") as movement_centrality_file,
                movement_stats_path.open("w", newline="", encoding="utf-8") as movement_stats_file,
                movement_gephi_nodes_path.open("w", newline="", encoding="utf-8") as movement_gephi_nodes_file,
                movement_gephi_edges_path.open("w", newline="", encoding="utf-8") as movement_gephi_edges_file,
            ):
                nodes_writer = csv.writer(movement_nodes_file)
                edges_writer = csv.writer(movement_edges_file)
                projected_writer = csv.writer(movement_projected_file)
                centrality_writer = csv.writer(movement_centrality_file)
                stats_writer = csv.writer(movement_stats_file)
                gephi_nodes_writer = csv.writer(movement_gephi_nodes_file)
                gephi_edges_writer = csv.writer(movement_gephi_edges_file)

                nodes_writer.writerow(["node_id", "node_type", "label", "degree"])
                edges_writer.writerow(["painting_id", "motif", "weight"])
                projected_writer.writerow(["motif_a", "motif_b", "shared_paintings"])
                gephi_nodes_writer.writerow(["id", "label"])
                gephi_edges_writer.writerow(["source", "target", "weight"])
                centrality_writer.writerow(
                    [
                        "motif",
                        "degree_centrality",
                        "weighted_degree",
                        "betweenness_centrality",
                        "closeness_centrality",
                        "eigenvector_centrality",
                        "pagerank",
                    ]
                )
                stats_writer.writerow(
                    [
                        "art_movement",
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

                for node_id, attrs in graph.nodes(data=True):
                    nodes_writer.writerow(
                        [
                            node_id,
                            attrs.get("node_type", ""),
                            attrs.get("label", ""),
                            graph.degree(node_id),
                        ]
                    )

                for painting_id, motif_id, attrs in graph.edges(data=True):
                    painting_node = painting_id if painting_id.startswith("painting::") else motif_id
                    motif_node = motif_id if motif_id.startswith("motif::") else painting_id
                    edges_writer.writerow(
                        [
                            painting_node,
                            graph.nodes[motif_node]["label"],
                            attrs.get("weight", 1),
                        ]
                    )

                for node_u, node_v, attrs in projected.edges(data=True):
                    label_u = projected.nodes[node_u]["label"]
                    label_v = projected.nodes[node_v]["label"]
                    projected_writer.writerow(
                        [
                            label_u,
                            label_v,
                            attrs.get("weight", 0),
                        ]
                    )
                    gephi_edges_writer.writerow([label_u, label_v, attrs.get("weight", 0)])

                for node in motif_nodes:
                    label = projected.nodes[node]["label"]
                    gephi_nodes_writer.writerow([label, label])

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

                ranked_motifs = sorted(
                    motif_nodes,
                    key=lambda node: (
                        weighted_degree.get(node, 0),
                        degree_centrality.get(node, 0.0),
                        pagerank.get(node, 0.0),
                    ),
                    reverse=True,
                )
                for node in ranked_motifs:
                    centrality_writer.writerow(
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
                stats_writer.writerow(
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

            summary_writer.writerow(
                [
                    movement,
                    len(painting_nodes),
                    len(motif_nodes),
                    graph.number_of_edges(),
                    projected.number_of_edges(),
                ]
            )
            print(f"Wrote: {movement_nodes_path}")
            print(f"Wrote: {movement_edges_path}")
            print(f"Wrote: {movement_projected_path}")
            print(f"Wrote: {movement_centrality_path}")
            print(f"Wrote: {movement_stats_path}")
            print(f"Wrote: {movement_gephi_nodes_path}")
            print(f"Wrote: {movement_gephi_edges_path}")

    print(f"Wrote: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
