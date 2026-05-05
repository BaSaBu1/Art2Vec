"""
embed_paintings.py — Phase 2: Laplacian Eigenmap embedding of paintings.

Builds a painting-painting k-NN similarity graph from three feature signals
(motif presence, HSV color profile, genre/nationality metadata), then places
each painting in 2D space via the eigenvectors of the normalized graph Laplacian.
"""

import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, diags, eye as speye
from scipy.sparse.linalg import eigsh
from sklearn.neighbors import NearestNeighbors
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MOVEMENTS = [
    ("Baroque",              "baroque"),
    ("Cubism",               "cubism"),
    ("Impressionism",        "impressionism"),
    ("Northern Renaissance", "northern_renaissance"),
    ("Romanticism",          "romanticism"),
]

N_NEIGHBORS  = 10     # k-NN: neighbors per painting in the similarity graph
N_DIMS       = 5      # number of Laplacian eigenvectors to compute
MIN_SIM      = 0.05   # drop edges with cosine similarity below this threshold
N_BINS       = 108    # total HSV color bins (12 hue × 3 sat × 3 val)
TOP_N_CATS   = 10     # how many top genres/nationalities to keep as explicit columns

# Feature block weights: motif 40%, color 40%, metadata 20%.
# Scaling each block by sqrt(w) before concatenation gives
# cosine(X_i, X_j) ≈ 0.4·motif_cos + 0.4·color_cos + 0.2·meta_cos.
MOTIF_WEIGHT = 0.4
COLOR_WEIGHT = 0.4
META_WEIGHT  = 0.2

MOVEMENT_COLORS = {
    "Baroque":              "#8B4513",
    "Cubism":               "#4169E1",
    "Impressionism":        "#2E8B57",
    "Northern Renaissance": "#8B008B",
    "Romanticism":          "#B22222",
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_motif_features(movement_folder):
    """Binary painting × motif matrix from Phase 1 bipartite network edges."""
    edges_path = os.path.join(
        "motif", "by_movement", movement_folder, "motif_painting_edges.csv"
    )
    df = pd.read_csv(edges_path)
    df["path"]    = df["painting_id"].str.replace("painting::", "", regex=False)
    df["present"] = 1
    pivot = df.pivot_table(
        index="path", columns="motif", values="present", fill_value=0
    )
    return pivot


def load_color_features(movement_folder):
    """HSV bin percentage vectors and display metadata for each painting."""
    color_path = os.path.join(
        "color", "by_movement", movement_folder, "extraction", "color_network_base.tsv"
    )
    df = pd.read_csv(color_path, sep="\t")

    vecs, metas = [], []
    for _, row in df.iterrows():
        vec = np.zeros(N_BINS, dtype=np.float32)
        try:
            bin_ids = [int(x) for x in str(row["ColorBinIds"]).split(",")]
            pcts    = [float(x) for x in str(row["ColorTagsPct"]).split(",")]
            for b, p in zip(bin_ids, pcts):
                if 0 <= b < N_BINS:
                    vec[b] = p
        except (ValueError, AttributeError):
            pass
        p = str(row["Path"])
        vecs.append({"path": p, **{f"bin_{i}": vec[i] for i in range(N_BINS)}})
        metas.append({
            "path":          p,
            "author_name":   str(row.get("author_name", "")),
            "painting_name": str(row.get("painting_name", "")),
            "image_url":     str(row.get("image_url", "")),
        })

    feat_df = pd.DataFrame(vecs).set_index("path")
    meta_df = pd.DataFrame(metas).set_index("path")
    return feat_df, meta_df


def load_metadata_raw(movement_folder):
    """Genre and nationality strings (first value when comma-separated) indexed by path."""
    color_path = os.path.join(
        "color", "by_movement", movement_folder, "extraction", "color_network_base.tsv"
    )
    df = pd.read_csv(color_path, sep="\t", usecols=["Path", "Genre", "Nationality"])
    df["genre"]       = df["Genre"].fillna("").str.split(",").str[0].str.strip().str.lower()
    df["nationality"] = df["Nationality"].fillna("").str.split(",").str[0].str.strip().str.lower()
    return df.rename(columns={"Path": "path"}).set_index("path")[["genre", "nationality"]]


def encode_metadata(meta_raw_df, top_genres=None, top_nats=None):
    """One-hot encode genre and nationality; returns (feature_df, top_genres, top_nats)."""
    if top_genres is None:
        top_genres = meta_raw_df["genre"].value_counts().head(TOP_N_CATS).index.tolist()
    if top_nats is None:
        top_nats = meta_raw_df["nationality"].value_counts().head(TOP_N_CATS).index.tolist()

    feat_df = pd.DataFrame(index=meta_raw_df.index, dtype=np.float32)
    for g in top_genres:
        feat_df[f"genre_{g}"] = (meta_raw_df["genre"] == g).astype(np.float32)
    feat_df["genre_other"] = (~meta_raw_df["genre"].isin(top_genres)).astype(np.float32)
    for n in top_nats:
        feat_df[f"nat_{n}"] = (meta_raw_df["nationality"] == n).astype(np.float32)
    feat_df["nat_other"] = (~meta_raw_df["nationality"].isin(top_nats)).astype(np.float32)

    return feat_df, top_genres, top_nats


# ---------------------------------------------------------------------------
# Feature matrix construction
# ---------------------------------------------------------------------------

def _l2_normalize(mat):
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return np.where(norms > 0, mat / norms, 0.0)


def build_combined_features(motif_df, color_df, meta_onehot_df):
    """
    Merge the three feature blocks on shared painting paths and concatenate
    with sqrt(weight) scaling so cosine similarity decomposes as
    0.4·motif + 0.4·color + 0.2·metadata.
    Returns (X, paths).
    """
    common = (
        motif_df.index
        .intersection(color_df.index)
        .intersection(meta_onehot_df.index)
    )
    if len(common) == 0:
        raise ValueError("No paintings shared across motif, color, and metadata.")

    M = motif_df.loc[common].values.astype(np.float32)
    C = color_df.loc[common].values.astype(np.float32)
    D = meta_onehot_df.loc[common].values.astype(np.float32)

    X = np.hstack([
        np.sqrt(MOTIF_WEIGHT) * _l2_normalize(M),
        np.sqrt(COLOR_WEIGHT) * _l2_normalize(C),
        np.sqrt(META_WEIGHT)  * _l2_normalize(D),
    ]).astype(np.float32)
    # Each row already has unit norm (weights sum to 1), so no final normalization.
    return X, list(common)


# ---------------------------------------------------------------------------
# Graph and embedding
# ---------------------------------------------------------------------------

def build_knn_graph(X):
    """Cosine k-NN similarity graph; edges below MIN_SIM are dropped. Returns CSR matrix."""
    n = X.shape[0]
    k = min(N_NEIGHBORS + 1, n - 1)

    nn = NearestNeighbors(n_neighbors=k, metric="cosine", algorithm="auto", n_jobs=-1)
    nn.fit(X)
    distances, indices = nn.kneighbors(X)

    rows, cols, vals = [], [], []
    for i in range(n):
        for j_pos in range(1, len(indices[i])):
            j   = indices[i][j_pos]
            sim = float(max(0.0, 1.0 - distances[i][j_pos]))
            if sim >= MIN_SIM:
                rows += [i, j]
                cols += [j, i]
                vals += [sim, sim]

    A = csr_matrix((vals, (rows, cols)), shape=(n, n))
    return A.maximum(A.T)


def compute_laplacian_embedding(A):
    """
    Normalized graph Laplacian L = I − D^{-1/2} A D^{-1/2}.
    Returns (embedding, eigenvalues); embedding columns are eigenvectors 2..N_DIMS+1
    (eigenvector 1 is the trivial all-ones vector and is discarded).
    """
    n = A.shape[0]
    d = np.asarray(A.sum(axis=1)).flatten()
    d_inv_sqrt = np.where(d > 0, 1.0 / np.sqrt(d), 0.0)
    D_inv_sqrt = diags(d_inv_sqrt, format="csr")
    L_norm = speye(n, format="csr") - D_inv_sqrt @ A @ D_inv_sqrt

    k = min(N_DIMS + 1, n - 2)
    eigenvalues, eigenvectors = eigsh(L_norm, k=k, which="SM", tol=1e-6, maxiter=3000)

    order        = np.argsort(eigenvalues)
    eigenvalues  = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    return eigenvectors[:, 1:N_DIMS + 1], eigenvalues


def find_medoid(embedding_2d):
    """Index of the painting closest to the 2D centroid of the cluster."""
    centroid = embedding_2d.mean(axis=0)
    return int(np.argmin(np.linalg.norm(embedding_2d - centroid, axis=1)))


# ---------------------------------------------------------------------------
# Per-movement pipeline
# ---------------------------------------------------------------------------

def embed_movement(movement_label, movement_folder,
                   global_motifs=None, global_color_cols=None,
                   global_top_genres=None, global_top_nats=None,
                   global_meta_cols=None):
    """Run the full embedding pipeline for one art movement; return results dict."""
    print(f"  Loading features...")
    motif_df           = load_motif_features(movement_folder)
    color_df, meta_df  = load_color_features(movement_folder)
    meta_raw           = load_metadata_raw(movement_folder)

    if global_motifs is not None:
        motif_df = motif_df.reindex(columns=global_motifs, fill_value=0)
    if global_color_cols is not None:
        color_df = color_df.reindex(columns=global_color_cols, fill_value=0.0)

    meta_onehot, top_genres, top_nats = encode_metadata(
        meta_raw,
        top_genres=global_top_genres,
        top_nats=global_top_nats,
    )
    if global_meta_cols is not None:
        meta_onehot = meta_onehot.reindex(columns=global_meta_cols, fill_value=0.0)

    print(f"  Paintings — motif: {len(motif_df)}, color: {len(color_df)}")
    print(f"  Building combined feature matrix...")
    X, paths = build_combined_features(motif_df, color_df, meta_onehot)
    print(f"  Paintings with all three signals: {len(paths)}")

    print(f"  Building k-NN graph (k={N_NEIGHBORS})...")
    A = build_knn_graph(X)
    n_edges = A.nnz // 2
    print(f"  Graph: {A.shape[0]} nodes, {n_edges} edges")

    print(f"  Computing graph Laplacian eigenvectors...")
    embedding, eigenvalues = compute_laplacian_embedding(A)
    print(f"  Eigenvalues: {np.round(eigenvalues[:6], 5)}")

    embedding_2d = embedding[:, :2]
    medoid_idx   = find_medoid(embedding_2d)

    out_dir = os.path.join("embedding", "by_movement", movement_folder)
    os.makedirs(out_dir, exist_ok=True)

    meta_aligned = meta_df.reindex(paths)
    coords_df = pd.DataFrame({
        "path":          paths,
        "author_name":   meta_aligned["author_name"].values,
        "painting_name": meta_aligned["painting_name"].values,
        "image_url":     meta_aligned["image_url"].values,
        "x":             embedding_2d[:, 0],
        "y":             embedding_2d[:, 1],
    })
    coords_df.to_csv(os.path.join(out_dir, "embedding_coords.csv"), index=False)

    medoid_row = coords_df.iloc[medoid_idx].copy()
    medoid_df  = pd.DataFrame([medoid_row])
    medoid_df["art_movement"]  = movement_label
    medoid_df["n_paintings"]   = len(paths)
    medoid_df["graph_edges"]   = n_edges
    medoid_df["fiedler_value"] = float(eigenvalues[1]) if len(eigenvalues) > 1 else np.nan
    medoid_df.to_csv(os.path.join(out_dir, "medoid.csv"), index=False)

    print(f"  Medoid: '{medoid_row['painting_name']}' by {medoid_row['author_name']}")

    color = MOVEMENT_COLORS.get(movement_label, "#888888")
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(embedding_2d[:, 0], embedding_2d[:, 1],
               s=6, alpha=0.35, color=color)
    centroid = embedding_2d.mean(axis=0)
    ax.scatter(centroid[0], centroid[1],
               s=80, marker="+", color="black", linewidths=1.8,
               label="centroid", zorder=4)
    ax.scatter(embedding_2d[medoid_idx, 0], embedding_2d[medoid_idx, 1],
               s=140, color="gold", edgecolors="black", linewidths=1.2,
               label=f"medoid\n'{medoid_row['painting_name'][:30]}...'", zorder=5)
    ax.set_title(f"{movement_label} — Laplacian Eigenmap (2D)", fontsize=13)
    ax.set_xlabel("Eigenvector 2  (Fiedler direction)")
    ax.set_ylabel("Eigenvector 3")
    ax.legend(fontsize=8, loc="best")
    ax.set_aspect("equal", adjustable="datalim")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "embedding_scatter.png"), dpi=150)
    plt.close()

    return {
        "movement":    movement_label,
        "embedding":   embedding,
        "paths":       paths,
        "meta":        meta_aligned,
        "medoid_idx":  medoid_idx,
        "medoid_row":  medoid_row,
        "top_genres":  top_genres,
        "top_nats":    top_nats,
    }


# ---------------------------------------------------------------------------
# Cross-movement embedding
# ---------------------------------------------------------------------------

def embed_cross_movement():
    """Embed all five movements in a shared 2D space using a common feature vocabulary."""
    print("\n" + "="*60)
    print("Cross-movement embedding (all movements together)")
    print("="*60)

    all_motif, all_color, all_meta_display, all_meta_raw = {}, {}, {}, {}
    for label, folder in MOVEMENTS:
        all_motif[label]               = load_motif_features(folder)
        all_color[label], all_meta_display[label] = load_color_features(folder)
        all_meta_raw[label]            = load_metadata_raw(folder)

    # Build global vocabularies so every movement uses the same columns
    global_motifs      = sorted({col for df in all_motif.values() for col in df.columns})
    global_color_cols  = [f"bin_{i}" for i in range(N_BINS)]

    combined_raw = pd.concat(all_meta_raw.values())
    global_top_genres  = combined_raw["genre"].value_counts().head(TOP_N_CATS).index.tolist()
    global_top_nats    = combined_raw["nationality"].value_counts().head(TOP_N_CATS).index.tolist()

    # Encode metadata globally and determine the shared one-hot column set
    sample_onehot, _, _ = encode_metadata(combined_raw, global_top_genres, global_top_nats)
    global_meta_cols = list(sample_onehot.columns)

    motif_parts, color_parts, meta_parts, label_list = [], [], [], []
    for label, _ in MOVEMENTS:
        m = all_motif[label].reindex(columns=global_motifs, fill_value=0)
        c = all_color[label].reindex(columns=global_color_cols, fill_value=0.0)
        d_raw = all_meta_raw[label]
        d, _, _ = encode_metadata(d_raw, global_top_genres, global_top_nats)
        d = d.reindex(columns=global_meta_cols, fill_value=0.0)
        common = m.index.intersection(c.index).intersection(d.index)
        motif_parts.append(m.loc[common])
        color_parts.append(c.loc[common])
        meta_parts.append(d.loc[common])
        label_list.extend([label] * len(common))

    motif_all = pd.concat(motif_parts)
    color_all  = pd.concat(color_parts)
    meta_all   = pd.concat(meta_parts)

    print(f"  Total paintings across all movements: {len(motif_all)}")
    X, paths = build_combined_features(motif_all, color_all, meta_all)
    labels_arr = np.array(label_list[:len(paths)])

    A = build_knn_graph(X)
    print(f"  Cross-movement graph: {A.shape[0]} nodes, {A.nnz // 2} edges")

    embedding, eigenvalues = compute_laplacian_embedding(A)
    print(f"  Eigenvalues: {np.round(eigenvalues[:6], 5)}")

    out_dir = "embedding"
    meta_display_all = pd.concat(all_meta_display.values())
    meta_aligned = meta_display_all.reindex(paths)
    cross_df = pd.DataFrame({
        "path":          paths,
        "art_movement":  labels_arr,
        "author_name":   meta_aligned["author_name"].values,
        "painting_name": meta_aligned["painting_name"].values,
        "x":             embedding[:, 0],
        "y":             embedding[:, 1],
    })
    cross_df.to_csv(os.path.join(out_dir, "cross_movement_embedding_coords.csv"), index=False)

    fig, ax = plt.subplots(figsize=(10, 7))
    for label, _ in MOVEMENTS:
        mask = cross_df["art_movement"] == label
        ax.scatter(
            cross_df.loc[mask, "x"], cross_df.loc[mask, "y"],
            s=5, alpha=0.30,
            color=MOVEMENT_COLORS.get(label, "#888"),
            label=label,
        )
    ax.set_title("All Movements — Laplacian Eigenmap (2D)", fontsize=13)
    ax.set_xlabel("Eigenvector 2  (Fiedler direction)")
    ax.set_ylabel("Eigenvector 3")
    ax.legend(fontsize=9, markerscale=4, framealpha=0.7)
    ax.set_aspect("equal", adjustable="datalim")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "cross_movement_scatter.png"), dpi=150)
    plt.close()

    print(f"  Saved: {out_dir}/cross_movement_embedding_coords.csv")
    print(f"  Saved: {out_dir}/cross_movement_scatter.png")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run Phase 2 embedding for all five art movements."""
    os.makedirs("embedding", exist_ok=True)
    overall_start = time.time()
    medoid_rows = []

    for movement_label, movement_folder in MOVEMENTS:
        print(f"\n{'='*60}")
        print(f"Movement: {movement_label}")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            result = embed_movement(movement_label, movement_folder)
            medoid_rows.append({
                "art_movement":  movement_label,
                "path":          result["medoid_row"]["path"],
                "author_name":   result["medoid_row"]["author_name"],
                "painting_name": result["medoid_row"]["painting_name"],
                "image_url":     result["medoid_row"]["image_url"],
                "x":             result["medoid_row"]["x"],
                "y":             result["medoid_row"]["y"],
            })
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
        print(f"  Finished in {time.time() - t0:.1f}s")

    if medoid_rows:
        summary = pd.DataFrame(medoid_rows)
        summary.to_csv(os.path.join("embedding", "medoids_summary.csv"), index=False)
        print("\n" + "="*60)
        print("MEDOIDS SUMMARY")
        print("="*60)
        print(summary[["art_movement", "painting_name", "author_name"]].to_string(index=False))

    embed_cross_movement()

    print(f"\nPhase 2 complete. Total time: {time.time() - overall_start:.1f}s")


if __name__ == "__main__":
    main()
