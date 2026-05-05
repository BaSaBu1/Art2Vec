export type Mode = 'explore' | 'analysis';
export type CentralityMetric = 'weightedDegree' | 'betweenness' | 'eigenvector';

export interface Movement {
  id: string;
  label: string;
  shortLabel: string;
  years: string;
  accent: string;
  description: string;
  featuredPaintingId?: string;
  paintings: number;
  embeddedPaintings: number;
  uniqueMotifs: number;
  motifEdges: number;
  colorNodes: number;
  colorEdges: number;
  motifBipartiteEdges: number;
  colorBipartiteEdges: number;
}

export interface PaintingColor {
  hex: string;
  pct: number;
}

export interface Painting {
  id: string;
  path: string;
  title: string;
  artist: string;
  imageUrl: string;
  movement: string;
  date: string;
  year: string;
  location: string;
  dimensions: string;
  media: string;
  genre: string;
  style: string;
  nationality: string;
  motifs: string[];
  colors: PaintingColor[];
  embedding?: { x: number; y: number } | null;
}

export interface CentralityItem {
  id: string;
  label: string;
  weightedDegree: number;
  betweenness: number;
  eigenvector: number;
}

export interface MotifGraphNode {
  id: string;
  label: string;
  shortLabel: string;
  x: number;
  y: number;
  radius: number;
  weightedDegree: number;
  community: number;
}

export interface MotifGraphEdge {
  source: string;
  target: string;
  weight: number;
  strength: number;
}

export interface CommunitySummary {
  id: number;
  color: string;
  topMotifs: string[];
  description: string;
}

export interface PaintingExample {
  id: string;
  title: string;
  artist: string;
  imageUrl: string;
  year: string;
}

export interface MotifGraph {
  width: number;
  height: number;
  modularity: number;
  nodes: MotifGraphNode[];
  edges: MotifGraphEdge[];
  communities: CommunitySummary[];
  motifExamples: Record<string, PaintingExample[]>;
}

export interface ColorCell {
  rank: number | null;
  paintingCount: number;
  examples: PaintingExample[];
}

export interface ColorRankRow {
  hex: string;
  cells: Record<string, ColorCell>;
}

export interface DistinctiveColor {
  hex: string;
  rank: number;
  paintingCount: number;
  lift: number;
  examples: PaintingExample[];
}

export interface EmbeddingPoint {
  id: string;
  movement: string;
  x: number;
  y: number;
  isMedoid: boolean;
}

export interface Medoid {
  paintingId: string;
  title: string;
  artist: string;
  imageUrl: string;
  year: string;
  x: number;
  y: number;
  graphEdges?: number;
  fiedler?: number;
}

export interface ArtData {
  schemaVersion: number;
  movements: Movement[];
  paintings: Painting[];
  analysis: {
    centrality: Record<string, Record<CentralityMetric, CentralityItem[]>>;
    motifGraphs: Record<string, MotifGraph>;
    colors: {
      rankTable: ColorRankRow[];
      distinctive: Record<string, DistinctiveColor[]>;
    };
    embedding: {
      points: EmbeddingPoint[];
      medoids: Record<string, Medoid>;
    };
  };
}
