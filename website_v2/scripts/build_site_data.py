from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import networkx as nx


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website_v2"


MOVEMENTS = [
    {
        "id": "northern_renaissance",
        "label": "Northern Renaissance",
        "shortLabel": "N. Renaissance",
        "years": "c. 1430-1580",
        "accent": "#7e8f57",
        "description": "Northern European oil painting sharpened realism, surface detail, devotional symbolism, and everyday interiors into a dense visual language.",
        "folder": "northern_renaissance",
    },
    {
        "id": "baroque",
        "label": "Baroque",
        "shortLabel": "Baroque",
        "years": "c. 1600-1750",
        "accent": "#9f5138",
        "description": "Baroque painting pushed drama, theatrical light, bodily motion, and religious or civic spectacle into emotionally charged compositions.",
        "folder": "baroque",
    },
    {
        "id": "romanticism",
        "label": "Romanticism",
        "shortLabel": "Romanticism",
        "years": "c. 1800-1850",
        "accent": "#6d738d",
        "description": "Romanticism centered intense feeling, the sublime, political struggle, distant histories, and the unstable force of nature.",
        "folder": "romanticism",
    },
    {
        "id": "impressionism",
        "label": "Impressionism",
        "shortLabel": "Impressionism",
        "years": "c. 1865-1885",
        "accent": "#b9925a",
        "description": "Impressionism treated modern life, open air, water, streets, leisure, and changing light through quick visible color.",
        "folder": "impressionism",
    },
    {
        "id": "cubism",
        "label": "Cubism",
        "shortLabel": "Cubism",
        "years": "c. 1907-1914",
        "accent": "#577f78",
        "description": "Cubism broke objects into planes, compressed multiple viewpoints, and rebuilt figures and still lifes as geometric structure.",
        "folder": "cubism",
    },
]

MOVEMENT_BY_LABEL = {item["label"]: item for item in MOVEMENTS}
MOVEMENT_BY_ID = {item["id"]: item for item in MOVEMENTS}
MOVEMENT_ORDER = [item["id"] for item in MOVEMENTS]

POPULAR_PATHS = {
    "northern_renaissance": [
        "Artists2/Hieronymus Bosch/The Garden Of Earthly Delights.jpg",
        "Artists2/Pieter Bruegel The Elder/Hunters In The Snow 1565.jpg",
        "Artists2/Jan Van Eyck/The Arnolfini Wedding The Portrait Of Giovanni Arnolfini And His Wife Giovanna Cenami The 1434.jpg",
    ],
    "baroque": [
        "Artists2/Diego Velazquez/Las Meninas Detail Of The Lower Half Depicting The Family Of Philip Iv Of Spain 1656.jpg",
        "Artists2/Hendrick Terbrugghen/The Calling Of St Matthew.jpg",
    ],
    "romanticism": [
        "Artists2/Eugene Delacroix/The Liberty Leading The People 1830.jpg",
        "Artists2/Francisco Goya/The Third Of May 1808 Execution Of The Defenders Of Madrid 1814 1.jpg",
        "Artists2/Theodore Gericault/The Raft Of The Medusa 1819.jpg",
    ],
    "impressionism": [
        "Artists2/Mary Cassatt/The Boating Party 1894.jpg",
        "Artists2/Claude Monet/The Cliffs At Etretat 1886.jpg",
        "Artists2/Gustave Caillebotte/Yerres On The Pond Water Lilies.jpg",
    ],
    "cubism": [
        "Artists2/Pablo Picasso/The Girls Of Avignon 1907.jpg",
        "Artists2/Georges Braque/Violin And Palette 1909.jpg",
        "Artists2/Pablo Picasso/Portrait Of Ambroise Vollard 1910.jpg",
    ],
}

COMMUNITY_COLORS = [
    "#2f5061",
    "#9f5138",
    "#7e8f57",
    "#b9925a",
    "#6d738d",
    "#8f6f55",
    "#516b5d",
    "#8a5c70",
]

SMALL_TITLE_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

MOTIF_REPLACEMENTS = {
    "jesus": "Jesus",
    "christ": "Christ",
    "mary": "Mary",
    "virgin": "Virgin",
    "madonna": "Madonna",
    "christianity": "Christianity",
    "bible": "Bible",
}

ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\u00a0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return "" if value.lower() in {"nan", "none"} else value


def repair_mojibake(value: str) -> str:
    if "Ã" not in value and "Â" not in value:
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def smart_title(value: str | None) -> str:
    text = repair_mojibake(clean_text(value))
    if not text:
        return ""
    text = re.sub(r",\s*", ", ", text)
    text = re.sub(r"[_/-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = []
    for index, word in enumerate(text.split(" ")):
        if not word:
            continue
        parts = []
        for part in word.split("'"):
            lower = part.lower()
            if not part:
                parts.append(part)
            elif lower in MOTIF_REPLACEMENTS:
                parts.append(MOTIF_REPLACEMENTS[lower])
            elif lower in ROMAN_NUMERALS:
                parts.append(lower.upper())
            elif index > 0 and lower in SMALL_TITLE_WORDS:
                parts.append(lower)
            elif len(part) <= 3 and part.isupper():
                parts.append(part)
            else:
                parts.append(part[:1].upper() + part[1:].lower())
        words.append("'".join(parts))
    return " ".join(words)


def clean_title(value: str | None) -> str:
    title = repair_mojibake(clean_text(value))
    if "##" in title:
        title = title.split("##", 1)[0].strip()
    title = re.sub(r"\s+(1[3-9]\d{2}|20\d{2})(\s+\d+)$", r"\2", title).strip()
    title = re.sub(r"\s+(1[3-9]\d{2}|20\d{2})$", "", title).strip()
    return smart_title(title)


def clean_motif(value: str | None) -> str:
    return smart_title(value)


def short_label(value: str, limit: int = 18) -> str:
    if len(value) <= limit:
        return value
    clean = re.sub(r"\b(and|of|the|with|in)\b", "", value, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(limit - 3, 1)].rstrip() + "..."


def normalize_url(value: str | None) -> str:
    url = clean_text(value)
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def split_tags(value: str | None) -> list[str]:
    tags = []
    for part in re.split(r"[,;]", value or ""):
        tag = clean_motif(part)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def movement_id(value: str | None) -> str:
    text = clean_text(value)
    if text in MOVEMENT_BY_LABEL:
        return MOVEMENT_BY_LABEL[text]["id"]
    return text.lower().replace(" ", "_")


def painting_id(path: str) -> str:
    return hashlib.sha1(path.encode("utf-8", errors="ignore")).hexdigest()[:12]


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except ValueError:
        return default


def parse_colors(hexes: str | None, pcts: str | None) -> list[dict[str, Any]]:
    color_parts = [clean_text(item).lower() for item in (hexes or "").split(",") if clean_text(item)]
    pct_parts = [parse_float(item) for item in (pcts or "").split(",") if clean_text(item)]
    output = []
    for index, color in enumerate(color_parts):
        output.append({"hex": color, "pct": round(pct_parts[index], 4) if index < len(pct_parts) else 0})
    return output


def extract_year(*values: str | None) -> str:
    for value in values:
        match = re.search(r"(1[3-9]\d{2}|20\d{2})", clean_text(value))
        if match:
            return match.group(1)
    return ""


def clean_date(value: str | None) -> str:
    text = clean_text(value)
    return text if re.search(r"\d", text) else ""


def community_description(top_motifs: list[str]) -> str:
    text = " ".join(top_motifs).lower()
    categories = [
        (
            {"bull", "bulls", "horse", "horses", "hunting", "racing"},
            "Animals, myth, and ritual action.",
        ),
        (
            {"mythology", "mythological", "classical", "venus", "aphrodite", "apollo", "cupid", "psyche", "roman", "greek", "nude"},
            "Classical myth, love, and idealized bodies.",
        ),
        (
            {"allegories", "allegory", "symbols", "devils", "demons", "punishments", "tortures", "sins", "sinners"},
            "Allegory, sin, and punishment.",
        ),
        (
            {"dante", "virgil", "quixote", "rocinante", "panza", "fictional", "literary"},
            "Literary figures and dramatic journeys.",
        ),
        (
            {"adam", "eden", "old testament", "sketch", "sketches", "designs"},
            "Creation, animals, and study sheets.",
        ),
        (
            {"bathing", "swimming", "children", "couples", "female nude", "male nude", "nude"},
            "Bodies, leisure, and intimate scenes.",
        ),
        (
            {"christianity", "jesus", "christ", "virgin", "mary", "saint", "apostle", "religious", "bible", "angel", "crucifixion", "golgotha", "madonna"},
            "Religious figures and Christian narratives.",
        ),
        (
            {"mealtime", "mealtimes", "furniture", "decoration", "tavern", "taverns", "children", "room", "interior", "family"},
            "Interiors, leisure, and family life.",
        ),
        (
            {"portrait", "self portrait", "face", "figure", "female", "male", "woman", "man", "child", "family", "famous people"},
            "Figures, portraits, and social identity.",
        ),
        (
            {"landscape", "nature", "tree", "trees", "mountain", "sky", "forest", "garden", "field", "river", "rural"},
            "Landscape, nature, and open-air settings.",
        ),
        (
            {"city", "street", "architecture", "building", "interior", "room", "house", "church", "urban"},
            "Architecture, interiors, and built space.",
        ),
        (
            {"sea", "water", "boat", "ship", "beach", "coast", "harbor", "river"},
            "Water, travel, and coastal scenes.",
        ),
        (
            {"war", "battle", "soldier", "weapon", "horse", "hunting", "death", "violence"},
            "Conflict, movement, and dramatic action.",
        ),
        (
            {"animal", "bird", "dog", "horse", "cattle", "sheep", "lion", "fish"},
            "Animals and human relationships with nature.",
        ),
        (
            {"still life", "fruit", "flower", "table", "bottle", "glass", "music", "instrument", "violin", "guitar"},
            "Objects, still life, and studio arrangements.",
        ),
        (
            {"geometric", "cubist", "abstract", "shape", "fragment", "plane"},
            "Fragmented form and geometric structure.",
        ),
    ]
    scored = []
    for order, (keywords, description) in enumerate(categories):
        score = sum(1 for keyword in keywords if keyword in text)
        if score:
            scored.append((score, -order, description))
    if scored:
        scored.sort(reverse=True)
        return scored[0][2]
    if top_motifs:
        return smart_title(top_motifs[0]) + " and related motifs."
    return "A compact cluster of related motifs."


def read_metadata() -> dict[str, dict[str, str]]:
    rows = read_csv(ROOT / "data_clean" / "color_analysis_dataset.tsv", delimiter="\t")
    output = {}
    for row in rows:
        path = clean_text(row.get("Path"))
        if path:
            output[path] = row
    return output


def read_motif_edges() -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
    motif_by_path: dict[str, set[str]] = defaultdict(set)
    paths_by_motif: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for movement in MOVEMENTS:
        path = ROOT / "motif" / "by_movement" / movement["folder"] / "motif_painting_edges.csv"
        for row in read_csv(path):
            raw_path = clean_text(row.get("painting_id")).replace("painting::", "", 1)
            motif = clean_text(row.get("motif"))
            if raw_path and motif:
                motif_by_path[raw_path].add(motif)
                paths_by_motif[movement["id"]][motif].append(raw_path)
    return {key: sorted(value) for key, value in motif_by_path.items()}, paths_by_motif


def read_embedding_coords() -> dict[str, dict[str, float]]:
    coords = {}
    for row in read_csv(ROOT / "embedding" / "cross_movement_embedding_coords.csv"):
        path = clean_text(row.get("path"))
        if path:
            coords[path] = {"x": parse_float(row.get("x")), "y": parse_float(row.get("y"))}
    return coords


def build_paintings(
    metadata: dict[str, dict[str, str]],
    motif_by_path: dict[str, list[str]],
    embedding_coords: dict[str, dict[str, float]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    paintings_by_path: dict[str, dict[str, Any]] = {}
    color_examples: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    for movement in MOVEMENTS:
        base_path = ROOT / "color" / "by_movement" / movement["folder"] / "network" / "color_network_base_thresholded.tsv"
        for row in read_csv(base_path, delimiter="\t"):
            path = clean_text(row.get("Path"))
            if not path:
                continue
            meta = metadata.get(path, {})
            raw_title = clean_text(row.get("painting_name") or meta.get("painting_name"))
            title = clean_title(raw_title)
            artist = smart_title(row.get("author_name") or meta.get("author_name")) or "Unknown Artist"
            date = clean_date(meta.get("Date") or row.get("Date"))
            image_url = normalize_url(row.get("image_url") or meta.get("image_url"))
            if not image_url:
                continue
            raw_motifs = motif_by_path.get(path) or split_tags(meta.get("Tag") or row.get("Tag"))
            motifs = []
            for motif in raw_motifs:
                display_motif = clean_motif(motif)
                if display_motif and display_motif not in motifs:
                    motifs.append(display_motif)
            colors = parse_colors(row.get("ColorTagsHex"), row.get("ColorTagsPct"))
            mid = movement["id"]
            coords = embedding_coords.get(path)
            item = {
                "id": painting_id(path),
                "path": path,
                "title": title or "Untitled",
                "artist": artist,
                "imageUrl": image_url,
                "movement": mid,
                "date": date,
                "year": extract_year(date, raw_title),
                "location": smart_title(meta.get("Location")),
                "dimensions": clean_text(meta.get("Dimensions")),
                "media": smart_title(meta.get("Media") or row.get("Media")),
                "genre": smart_title(meta.get("Genre") or row.get("Genre")),
                "style": smart_title(meta.get("Style") or row.get("Style")),
                "nationality": smart_title(meta.get("Nationality") or row.get("Nationality")),
                "motifs": motifs[:14],
                "colors": colors[:9],
                "embedding": coords,
            }
            paintings_by_path[path] = item
            for color in colors:
                examples = color_examples[mid][color["hex"]]
                if len(examples) < 10:
                    examples.append(
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "artist": item["artist"],
                            "imageUrl": item["imageUrl"],
                            "year": item["year"],
                        }
                    )

    paintings = list(paintings_by_path.values())
    paintings.sort(
        key=lambda item: (
            MOVEMENT_ORDER.index(item["movement"]),
            item["artist"].lower(),
            item["title"].lower(),
        )
    )

    id_by_path = {item["path"]: item["id"] for item in paintings}
    return paintings, color_examples, id_by_path


def read_summaries() -> dict[str, dict[str, Any]]:
    motif_rows = {movement_id(row.get("art_movement")): row for row in read_csv(ROOT / "motif" / "motif_network_summary.csv")}
    color_rows = {movement_id(row.get("movement")): row for row in read_csv(ROOT / "color" / "color_network_summary.csv")}
    output = {}
    for movement in MOVEMENTS:
        mid = movement["id"]
        motif = motif_rows.get(mid, {})
        color = color_rows.get(mid, {})
        output[mid] = {
            "paintings": parse_int(color.get("painting_nodes")),
            "embeddedPaintings": 0,
            "uniqueMotifs": parse_int(motif.get("motif_nodes")),
            "motifEdges": parse_int(motif.get("projected_motif_edges")),
            "colorNodes": parse_int(color.get("color_nodes")),
            "colorEdges": parse_int(color.get("projected_edges")),
            "motifBipartiteEdges": parse_int(motif.get("bipartite_edges")),
            "colorBipartiteEdges": parse_int(color.get("bipartite_edges")),
        }
    return output


def read_centrality() -> dict[str, dict[str, list[dict[str, Any]]]]:
    output = {}
    for movement in MOVEMENTS:
        rows = []
        path = ROOT / "motif" / "by_movement" / movement["folder"] / "motif_centrality.csv"
        for row in read_csv(path):
            motif_id = clean_text(row.get("motif"))
            rows.append(
                {
                    "id": motif_id,
                    "label": clean_motif(motif_id),
                    "weightedDegree": parse_float(row.get("weighted_degree")),
                    "betweenness": parse_float(row.get("betweenness_centrality")),
                    "eigenvector": parse_float(row.get("eigenvector_centrality")),
                }
            )
        output[movement["id"]] = {
            "weightedDegree": sorted(rows, key=lambda item: item["weightedDegree"], reverse=True),
            "betweenness": sorted(rows, key=lambda item: item["betweenness"], reverse=True),
            "eigenvector": sorted(rows, key=lambda item: item["eigenvector"], reverse=True),
        }
    return output


def separate_nodes(nodes: list[dict[str, Any]], width: int, height: int) -> None:
    for _ in range(90):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a = nodes[i]
                b = nodes[j]
                dx = b["x"] - a["x"]
                dy = b["y"] - a["y"]
                dist = math.sqrt(dx * dx + dy * dy) or 0.001
                min_dist = a["radius"] + b["radius"] + 22
                if dist < min_dist:
                    push = (min_dist - dist) / 2
                    ux = dx / dist
                    uy = dy / dist
                    a["x"] -= ux * push
                    a["y"] -= uy * push
                    b["x"] += ux * push
                    b["y"] += uy * push
                    moved = True
        for node in nodes:
            node["x"] = min(max(node["x"], 70), width - 70)
            node["y"] = min(max(node["y"], 70), height - 70)
        if not moved:
            break


def build_motif_graphs(
    centrality: dict[str, dict[str, list[dict[str, Any]]]],
    paths_by_motif: dict[str, dict[str, list[str]]],
    paintings_by_id: dict[str, dict[str, Any]],
    id_by_path: dict[str, str],
) -> dict[str, Any]:
    graphs = {}
    for movement in MOVEMENTS:
        mid = movement["id"]
        folder = movement["folder"]
        edge_path = ROOT / "motif" / "by_movement" / folder / "motif_projected_edges.csv"
        graph = nx.Graph()
        for item in centrality[mid]["weightedDegree"]:
            graph.add_node(item["id"])
        for row in read_csv(edge_path):
            a = clean_text(row.get("motif_a"))
            b = clean_text(row.get("motif_b"))
            weight = parse_int(row.get("shared_paintings"))
            if a and b and weight:
                graph.add_edge(a, b, weight=weight)

        communities = nx.community.louvain_communities(graph, weight="weight", seed=42)
        community_by_node = {}
        for index, community in enumerate(communities):
            for node in community:
                community_by_node[node] = index

        width, height = 1560, 1080
        center_x, center_y = width / 2, height / 2
        ellipse_x, ellipse_y = width * 0.32, height * 0.28
        positioned: dict[str, tuple[float, float]] = {}
        ordered_communities = sorted(enumerate(communities), key=lambda item: len(item[1]), reverse=True)
        for ring_index, (community_index, community) in enumerate(ordered_communities):
            angle = (2 * math.pi * ring_index) / max(len(ordered_communities), 1) - math.pi / 2
            cx = center_x + math.cos(angle) * ellipse_x
            cy = center_y + math.sin(angle) * ellipse_y
            local = graph.subgraph(community)
            if local.number_of_nodes() <= 1:
                node = next(iter(community))
                positioned[node] = (cx, cy)
                continue
            local_positions = nx.spring_layout(local, weight="weight", seed=100 + community_index, iterations=520, k=0.74)
            xs = [xy[0] for xy in local_positions.values()]
            ys = [xy[1] for xy in local_positions.values()]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            span_x = max(max_x - min_x, 0.001)
            span_y = max(max_y - min_y, 0.001)
            cluster_radius = 130 + 14 * math.sqrt(len(community))
            for node, (x_raw, y_raw) in local_positions.items():
                positioned[node] = (
                    cx + (((x_raw - min_x) / span_x) - 0.5) * cluster_radius * 2.1,
                    cy + (((y_raw - min_y) / span_y) - 0.5) * cluster_radius * 1.75,
                )

        weighted_lookup = {item["id"]: item["weightedDegree"] for item in centrality[mid]["weightedDegree"]}
        max_weighted = max(weighted_lookup.values()) if weighted_lookup else 1
        nodes = []
        for node in graph.nodes:
            x_raw, y_raw = positioned[node]
            radius = 24 + 44 * math.sqrt(weighted_lookup.get(node, 0) / max_weighted)
            label = clean_motif(node)
            nodes.append(
                {
                    "id": node,
                    "label": label,
                    "shortLabel": short_label(label),
                    "x": x_raw,
                    "y": y_raw,
                    "radius": round(radius, 2),
                    "weightedDegree": weighted_lookup.get(node, 0),
                    "community": community_by_node.get(node, 0),
                }
            )
        separate_nodes(nodes, width, height)

        edges = [
            {"source": a, "target": b, "weight": int(data.get("weight", 1))}
            for a, b, data in graph.edges(data=True)
        ]
        max_edge = max((edge["weight"] for edge in edges), default=1)
        for edge in edges:
            edge["strength"] = round(0.35 + 6.15 * math.sqrt(edge["weight"] / max_edge), 3)

        modularity = nx.community.modularity(graph, communities, weight="weight") if graph.number_of_edges() else 0

        community_summaries = []
        for index, community in enumerate(communities):
            sorted_nodes = sorted(community, key=lambda node: weighted_lookup.get(node, 0), reverse=True)
            top = [clean_motif(node) for node in sorted_nodes[:5]]
            community_summaries.append(
                {
                    "id": index,
                    "color": COMMUNITY_COLORS[index % len(COMMUNITY_COLORS)],
                    "topMotifs": top,
                    "description": community_description(top),
                }
            )

        motif_examples = {}
        for motif, paths in paths_by_motif.get(mid, {}).items():
            examples = []
            for raw_path in paths:
                painting = paintings_by_id.get(id_by_path.get(raw_path, ""))
                if painting:
                    examples.append(
                        {
                            "id": painting["id"],
                            "title": painting["title"],
                            "artist": painting["artist"],
                            "imageUrl": painting["imageUrl"],
                            "year": painting["year"],
                        }
                    )
                if len(examples) >= 8:
                    break
            motif_examples[motif] = examples

        graphs[mid] = {
            "width": width,
            "height": height,
            "modularity": round(modularity, 3),
            "nodes": nodes,
            "edges": edges,
            "communities": community_summaries,
            "motifExamples": motif_examples,
        }
    return graphs


def build_color_analysis(color_examples: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    ranks_by_movement: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    appearances: Counter[str] = Counter()
    rank_sum: Counter[str] = Counter()
    count_sum: Counter[str] = Counter()

    for movement in MOVEMENTS:
        rows = read_csv(ROOT / "color" / "by_movement" / movement["folder"] / "extraction" / "color_tag_counts.csv")
        for index, row in enumerate(rows, start=1):
            color = clean_text(row.get("color_hex")).lower()
            count = parse_int(row.get("painting_count"))
            if not color:
                continue
            ranks_by_movement[movement["id"]][color] = {"rank": index, "paintingCount": count}
            if index <= 20:
                appearances[color] += 1
                rank_sum[color] += index
                count_sum[color] += count

    common_colors = sorted(
        appearances,
        key=lambda color: (-appearances[color], rank_sum[color] / max(appearances[color], 1), -count_sum[color]),
    )[:10]

    rank_table = []
    for color in common_colors:
        cells = {}
        for movement in MOVEMENTS:
            entry = ranks_by_movement[movement["id"]].get(color)
            examples = color_examples[movement["id"]].get(color, [])
            cells[movement["id"]] = {
                "rank": entry["rank"] if entry else None,
                "paintingCount": entry["paintingCount"] if entry else 0,
                "examples": examples,
            }
        rank_table.append({"hex": color, "cells": cells})

    distinctive: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_csv(ROOT / "color_analysis" / "results" / "distinctive_colors_lift.csv"):
        mid = movement_id(row.get("movement"))
        color = clean_text(row.get("color_hex")).lower()
        if mid in MOVEMENT_BY_ID and len(distinctive[mid]) < 8:
            distinctive[mid].append(
                {
                    "hex": color,
                    "rank": parse_int(row.get("rank")),
                    "paintingCount": parse_int(row.get("painting_count")),
                    "lift": round(parse_float(row.get("lift")), 2),
                    "examples": color_examples[mid].get(color, []),
                }
            )

    return {"rankTable": rank_table, "distinctive": distinctive}


def build_embedding(paintings_by_id: dict[str, dict[str, Any]], id_by_path: dict[str, str], summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    medoids = {}
    medoid_ids = set()
    for row in read_csv(ROOT / "embedding" / "medoids_summary.csv"):
        mid = movement_id(row.get("art_movement"))
        pid = id_by_path.get(clean_text(row.get("path")))
        if not pid:
            continue
        painting = paintings_by_id[pid]
        medoid_ids.add(pid)
        medoids[mid] = {
            "paintingId": pid,
            "title": painting["title"],
            "artist": painting["artist"],
            "imageUrl": painting["imageUrl"],
            "year": painting["year"],
            "x": parse_float(row.get("x")),
            "y": parse_float(row.get("y")),
        }

    for movement in MOVEMENTS:
        medoid_path = ROOT / "embedding" / "by_movement" / movement["folder"] / "medoid.csv"
        rows = read_csv(medoid_path)
        if rows:
            row = rows[0]
            summaries[movement["id"]]["embeddedPaintings"] = parse_int(row.get("n_paintings"))
            medoids.setdefault(movement["id"], {}).update(
                {
                    "graphEdges": parse_int(row.get("graph_edges")),
                    "fiedler": parse_float(row.get("fiedler_value")),
                }
            )

    points = []
    per_movement_seen = Counter()
    for row in read_csv(ROOT / "embedding" / "cross_movement_embedding_coords.csv"):
        path = clean_text(row.get("path"))
        pid = id_by_path.get(path)
        if not pid:
            continue
        mid = movement_id(row.get("art_movement"))
        digest = int(hashlib.sha1(path.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)
        include = pid in medoid_ids or digest % 17 == 0 or per_movement_seen[mid] < 80
        if include:
            per_movement_seen[mid] += 1
            points.append(
                {
                    "id": pid,
                    "movement": mid,
                    "x": parse_float(row.get("x")),
                    "y": parse_float(row.get("y")),
                    "isMedoid": pid in medoid_ids,
                }
            )
    return {"points": points, "medoids": medoids}


def build_featured(id_by_path: dict[str, str], medoids: dict[str, Any]) -> dict[str, str]:
    featured = {}
    for movement in MOVEMENTS:
        mid = movement["id"]
        for path in POPULAR_PATHS[mid]:
            if path in id_by_path:
                featured[mid] = id_by_path[path]
                break
        if mid not in featured and mid in medoids:
            featured[mid] = medoids[mid]["paintingId"]
    return featured


def main() -> None:
    metadata = read_metadata()
    motif_by_path, paths_by_motif = read_motif_edges()
    embedding_coords = read_embedding_coords()
    paintings, color_examples, id_by_path = build_paintings(metadata, motif_by_path, embedding_coords)
    paintings_by_id = {painting["id"]: painting for painting in paintings}
    summaries = read_summaries()
    centrality = read_centrality()
    embedding = build_embedding(paintings_by_id, id_by_path, summaries)
    featured = build_featured(id_by_path, embedding["medoids"])

    movement_payload = []
    for movement in MOVEMENTS:
        payload = {
            "id": movement["id"],
            "label": movement["label"],
            "shortLabel": movement["shortLabel"],
            "years": movement["years"],
            "accent": movement["accent"],
            "description": movement["description"],
            "featuredPaintingId": featured.get(movement["id"]),
        }
        payload.update(summaries[movement["id"]])
        movement_payload.append(payload)

    data = {
        "schemaVersion": 2,
        "movements": movement_payload,
        "paintings": paintings,
        "analysis": {
            "centrality": centrality,
            "motifGraphs": build_motif_graphs(centrality, paths_by_motif, paintings_by_id, id_by_path),
            "colors": build_color_analysis(color_examples),
            "embedding": embedding,
        },
    }

    output_path = SITE / "public" / "data" / "artData.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, separators=(",", ":"))

    print(f"Wrote {output_path.relative_to(ROOT)} with {len(paintings)} paintings.")


if __name__ == "__main__":
    main()
