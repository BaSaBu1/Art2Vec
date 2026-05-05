import { useEffect, useMemo, useRef, useState } from "react";
import {
    ArrowRight,
    Info,
    Maximize2,
    RotateCcw,
    Search,
    X,
} from "lucide-react";
import type {
    ArtData,
    CentralityItem,
    CentralityMetric,
    ColorCell,
    EmbeddingPoint,
    Mode,
    MotifGraph,
    MotifGraphNode,
    Movement,
    Painting,
    PaintingExample,
} from "./types";
import {
    centralityValue,
    formatNumber,
    paintingSearchText,
    percent,
} from "./lib/format";

const centralityTabs: { id: CentralityMetric; label: string; short: string }[] =
    [
        { id: "weightedDegree", label: "Weighted Degree", short: "Degree" },
        {
            id: "betweenness",
            label: "Betweenness Centrality",
            short: "Between",
        },
        { id: "eigenvector", label: "Eigenvector Centrality", short: "Eigen" },
    ];

const slides = ["Opening", "Scope", "Motifs", "Colors", "Embedding", "Close"];

const methodNotes = {
    motif: "Motifs are linked when they appear in the same paintings. Larger, more central motifs carry more of a movement's visual language.",
    color: "Painting pixels are grouped into shared color bins. The table follows how each color rises or falls across movements.",
    embedding:
        "Each point is a painting. Nearby points share more motifs, colors, genres, and origins.",
};

const colorNameByHex: Record<string, string> = {
    "#d4cbb1": "Warm Ivory",
    "#805040": "Umber Brown",
    "#807040": "Olive Ochre",
    "#d4bab1": "Pale Rose",
    "#80706b": "Warm Taupe",
    "#2a1a15": "Deep Umber",
    "#2a2523": "Charcoal Brown",
    "#d4ba6a": "Muted Gold",
    "#807b6b": "Stone Taupe",
    "#803116": "Burnt Sienna",
};

function colorName(hex: string) {
    return colorNameByHex[hex.toLowerCase()] ?? hex;
}

function App() {
    const [data, setData] = useState<ArtData | null>(null);
    const [dataError, setDataError] = useState("");
    const [entered, setEntered] = useState(false);
    const [mode, setMode] = useState<Mode>("explore");
    const [curtain, setCurtain] = useState<"idle" | "closing" | "opening">(
        "idle",
    );
    const [inspectedPaintingId, setInspectedPaintingId] = useState<
        string | null
    >(null);
    const transitioning = useRef(false);

    useEffect(() => {
        const controller = new AbortController();
        fetch(`${import.meta.env.BASE_URL}data/artData.json`, {
            signal: controller.signal,
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(`Data request failed: ${response.status}`);
                }
                return response.json() as Promise<ArtData>;
            })
            .then(setData)
            .catch((error: unknown) => {
                if ((error as Error).name !== "AbortError") {
                    setDataError(
                        error instanceof Error
                            ? error.message
                            : "Unable to load Art2Vec data.",
                    );
                }
            });

        return () => controller.abort();
    }, []);

    useEffect(() => {
        document.body.classList.toggle(
            "analysis-mode",
            entered && mode === "analysis",
        );
        return () => document.body.classList.remove("analysis-mode");
    }, [entered, mode]);

    const paintingsById = useMemo(() => {
        const map = new Map<string, Painting>();
        data?.paintings.forEach((painting) => map.set(painting.id, painting));
        return map;
    }, [data]);

    const inspectedPainting = inspectedPaintingId
        ? (paintingsById.get(inspectedPaintingId) ?? null)
        : null;

    const runCurtain = (action: () => void) => {
        if (transitioning.current) {
            return;
        }
        transitioning.current = true;
        setCurtain("closing");
        window.setTimeout(() => {
            action();
            setCurtain("opening");
            window.setTimeout(() => {
                setCurtain("idle");
                transitioning.current = false;
            }, 720);
        }, 520);
    };

    const enterApp = (targetMode: Mode) => {
        runCurtain(() => {
            setEntered(true);
            setMode(targetMode);
            window.scrollTo({ top: 0 });
        });
    };

    const switchMode = (targetMode: Mode) => {
        if (targetMode === mode) {
            return;
        }
        runCurtain(() => {
            setMode(targetMode);
            window.scrollTo({ top: 0 });
        });
    };

    const returnHome = () => {
        runCurtain(() => {
            setEntered(false);
            setInspectedPaintingId(null);
            window.scrollTo({ top: 0 });
        });
    };

    if (dataError) {
        return <Loading message={dataError} />;
    }

    if (!data) {
        return <Loading message="Loading paintings" />;
    }

    return (
        <>
            <div className={`curtain ${curtain}`} aria-hidden="true" />
            <Nav
                entered={entered}
                mode={mode}
                onHome={returnHome}
                onMode={switchMode}
            />

            {!entered ? (
                <Hero data={data} onEnter={enterApp} />
            ) : mode === "explore" ? (
                <Explore
                    data={data}
                    onInspectPainting={setInspectedPaintingId}
                />
            ) : (
                <Presentation
                    data={data}
                    onInspectPainting={setInspectedPaintingId}
                    onExplore={() => switchMode("explore")}
                />
            )}

            {inspectedPainting && (
                <PaintingModal
                    data={data}
                    painting={inspectedPainting}
                    onClose={() => setInspectedPaintingId(null)}
                    onInspectPainting={setInspectedPaintingId}
                />
            )}
        </>
    );
}

function Loading({ message }: { message: string }) {
    return (
        <div className="loading-shell">
            <LogoMark />
            <p>{message}</p>
        </div>
    );
}

function Nav({
    entered,
    mode,
    onHome,
    onMode,
}: {
    entered: boolean;
    mode: Mode;
    onHome: () => void;
    onMode: (mode: Mode) => void;
}) {
    return (
        <nav className="site-nav">
            <button
                type="button"
                className="nav-logo"
                onClick={onHome}
                aria-label="Return to Art2Vec opening"
            >
                <LogoMark />
                <span>Art2Vec</span>
            </button>
            {entered && (
                <div className="nav-modes" aria-label="Website mode">
                    <button
                        type="button"
                        className={mode === "explore" ? "active" : ""}
                        onClick={() => onMode("explore")}
                    >
                        Explore
                    </button>
                    <button
                        type="button"
                        className={mode === "analysis" ? "active" : ""}
                        onClick={() => onMode("analysis")}
                    >
                        Analysis
                    </button>
                </div>
            )}
        </nav>
    );
}

function LogoMark() {
    return (
        <svg
            className="logo-mark"
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            aria-hidden="true"
        >
            <circle
                cx="6"
                cy="22"
                r="2.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
            />
            <circle
                cx="22"
                cy="22"
                r="2.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
            />
            <circle
                cx="14"
                cy="6"
                r="2.5"
                fill="var(--accent)"
                stroke="var(--accent)"
                strokeWidth="1.2"
            />
            <line
                x1="8"
                y1="20"
                x2="13"
                y2="9"
                stroke="currentColor"
                strokeWidth="0.8"
            />
            <line
                x1="20"
                y1="20"
                x2="15"
                y2="9"
                stroke="currentColor"
                strokeWidth="0.8"
            />
            <line
                x1="9"
                y1="22"
                x2="19"
                y2="22"
                stroke="currentColor"
                strokeWidth="0.8"
            />
        </svg>
    );
}

function Hero({
    data,
    onEnter,
}: {
    data: ArtData;
    onEnter: (mode: Mode) => void;
}) {
    return (
        <main className="hero">
            <div className="hero-copy">
                <div className="hero-eyebrow">
                    <span className="label">
                        Spring 2026 - Macalester College - COMP 479
                    </span>
                </div>
                <h1 className="display hero-title">
                    <span className="hero-title-line">
                        <span>The mathematics</span>
                    </span>
                    <span className="hero-title-line">
                        <span>
                            of <em>art history.</em>
                        </span>
                    </span>
                </h1>
                <p className="hero-subtitle">
                    Mapping 16000+ paintings across five centuries through motif
                    networks, color structure, and geometric embeddings.
                </p>
                <div className="hero-cta">
                    <button
                        type="button"
                        className="btn-primary"
                        onClick={() => onEnter("explore")}
                    >
                        <span>Explore the collection</span>
                        <ArrowRight size={15} />
                    </button>
                    <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => onEnter("analysis")}
                    >
                        View analysis
                    </button>
                </div>
                <div className="hero-stats">
                    <Stat value="16000+" label="Paintings" />
                    <Stat
                        value={String(data.movements.length)}
                        label="Movements"
                    />
                    <Stat value="10" label="Networks" />
                    <Stat value="108" label="Color groups" />
                </div>
            </div>
            <ArtworkConstellation data={data} variant="hero" />
        </main>
    );
}

function Stat({ value, label }: { value: string; label: string }) {
    return (
        <div className="hero-stat">
            <span className="hero-stat-num">{value}</span>
            <span className="hero-stat-label">{label}</span>
        </div>
    );
}

function ArtworkConstellation({
    data,
    variant = "hero",
}: {
    data: ArtData;
    variant?: "hero" | "slide";
}) {
    const paintings = useMemo(
        () =>
            data.movements
                .map((movement) =>
                    randomItem(
                        data.paintings.filter(
                            (painting) =>
                                painting.movement === movement.id &&
                                painting.imageUrl,
                        ),
                    ),
                )
                .filter((painting): painting is Painting => Boolean(painting)),
        [data],
    );

    return (
        <div
            className={`art-constellation ${variant} ${variant === "slide" ? "slide-content" : ""}`}
            aria-label="Featured paintings from the five movements"
        >
            {paintings.map((painting, index) => (
                <figure
                    key={painting.id}
                    className={`constellation-card card-${index + 1}`}
                    style={
                        {
                            "--card-delay": `${index * 0.08}s`,
                        } as React.CSSProperties
                    }
                >
                    <PaintingImage
                        src={painting.imageUrl}
                        alt={painting.title}
                    />
                    <figcaption>{painting.title}</figcaption>
                </figure>
            ))}
            <svg viewBox="0 0 420 420" aria-hidden="true">
                <path d="M98 110 C160 52, 265 58, 326 140" />
                <path d="M94 124 C60 192, 74 274, 150 326" />
                <path d="M326 142 C366 210, 332 294, 272 338" />
                <path d="M148 326 C190 382, 246 382, 274 338" />
                <path d="M88 246 C164 166, 244 146, 342 226" />
                <path d="M170 94 C216 188, 226 248, 206 342" />
            </svg>
        </div>
    );
}

function randomItem<T>(items: T[]) {
    if (!items.length) {
        return undefined;
    }
    return items[Math.floor(Math.random() * items.length)];
}

function Explore({
    data,
    onInspectPainting,
}: {
    data: ArtData;
    onInspectPainting: (id: string) => void;
}) {
    const [movement, setMovement] = useState("all");
    const [query, setQuery] = useState("");
    const movementById = useMemo(
        () => new Map(data.movements.map((item) => [item.id, item])),
        [data.movements],
    );
    const shuffledPaintings = useMemo(() => {
        const output = [...data.paintings];
        for (let index = output.length - 1; index > 0; index -= 1) {
            const swapIndex = Math.floor(Math.random() * (index + 1));
            [output[index], output[swapIndex]] = [
                output[swapIndex],
                output[index],
            ];
        }
        return output;
    }, [data.paintings]);

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase();
        return shuffledPaintings.filter((painting) => {
            const movementOk =
                movement === "all" || painting.movement === movement;
            const queryOk = !q || paintingSearchText(painting).includes(q);
            return movementOk && queryOk;
        });
    }, [movement, query, shuffledPaintings]);

    const visible = filtered.slice(0, 260);

    return (
        <main className="explore-shell">
            <div className="explore-header">
                <div>
                    <div className="label">
                        Explore - {formatNumber(filtered.length)} matches
                    </div>
                    <h1 className="display">
                        The <em>collection.</em>
                    </h1>
                </div>
                <label className="explore-search">
                    <Search size={16} />
                    <input
                        type="search"
                        placeholder="Search title, artist, motif..."
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                    />
                </label>
            </div>

            <div className="explore-filters">
                <button
                    type="button"
                    className={movement === "all" ? "active" : ""}
                    onClick={() => setMovement("all")}
                >
                    All
                </button>
                {data.movements.map((item) => (
                    <button
                        type="button"
                        key={item.id}
                        className={movement === item.id ? "active" : ""}
                        onClick={() => setMovement(item.id)}
                    >
                        {item.label}
                    </button>
                ))}
            </div>

            <div className="explore-grid">
                {visible.map((painting, index) => {
                    const mv = movementById.get(painting.movement);
                    const hoverMeta = [
                        painting.date || painting.year,
                        painting.nationality,
                    ].filter(Boolean);
                    return (
                        <button
                            type="button"
                            key={painting.id}
                            className="explore-card"
                            onClick={() => onInspectPainting(painting.id)}
                            style={
                                {
                                    "--rise-delay": `${Math.min(index, 30) * 0.025}s`,
                                } as React.CSSProperties
                            }
                        >
                            <div className="explore-thumb">
                                <PaintingImage
                                    src={painting.imageUrl}
                                    alt={painting.title}
                                />
                                {hoverMeta.length > 0 && (
                                    <div className="hover-card-meta">
                                        {hoverMeta.map((item) => (
                                            <span key={item}>{item}</span>
                                        ))}
                                    </div>
                                )}
                            </div>
                            <div className="explore-info">
                                <div
                                    className="explore-info-mv"
                                    style={{ color: mv?.accent }}
                                >
                                    {mv?.label}
                                </div>
                                <div className="explore-info-title">
                                    {painting.title}
                                </div>
                                <div className="explore-info-meta">
                                    {painting.artist}
                                </div>
                            </div>
                        </button>
                    );
                })}
            </div>
        </main>
    );
}

function PaintingModal({
    data,
    painting,
    onClose,
    onInspectPainting,
}: {
    data: ArtData;
    painting: Painting;
    onClose: () => void;
    onInspectPainting: (id: string) => void;
}) {
    const movement = data.movements.find(
        (item) => item.id === painting.movement,
    );
    const similar = useMemo(
        () => findSimilarPaintings(painting, data.paintings).slice(0, 4),
        [data.paintings, painting],
    );

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                onClose();
            }
        };
        document.addEventListener("keydown", onKeyDown);
        document.body.classList.add("modal-open");
        return () => {
            document.removeEventListener("keydown", onKeyDown);
            document.body.classList.remove("modal-open");
        };
    }, [onClose]);

    return (
        <div
            className="detail-overlay open"
            onMouseDown={(event) =>
                event.target === event.currentTarget && onClose()
            }
        >
            <div className="detail-wrap">
                <button
                    type="button"
                    className="detail-close"
                    onClick={onClose}
                >
                    <X size={17} />
                    close
                </button>
                <div className="detail-card">
                    <div className="detail-image">
                        <PaintingImage
                            src={painting.imageUrl}
                            alt={painting.title}
                        />
                    </div>
                    <div className="detail-body">
                        <div className="detail-mv">
                            {movement?.label}
                            {painting.year ? ` - ${painting.year}` : ""}
                        </div>
                        <h2>{painting.title}</h2>
                        <p className="detail-artist">{painting.artist}</p>

                        <div className="detail-meta-grid">
                            <MaybeMeta
                                label="Date"
                                value={painting.date || painting.year}
                            />
                            <MaybeMeta
                                label="Origin"
                                value={painting.nationality}
                            />
                            <MaybeMeta
                                label="Dimensions"
                                value={painting.dimensions}
                            />
                            <MaybeMeta label="Medium" value={painting.media} />
                            <MaybeMeta label="Genre" value={painting.genre} />
                        </div>

                        <DetailSection label="Main Motifs">
                            <div className="motif-chips">
                                {painting.motifs.map((motif) => (
                                    <span key={motif}>{motif}</span>
                                ))}
                            </div>
                        </DetailSection>

                        <DetailSection label="Main Colors">
                            <div className="color-swatches-row">
                                {painting.colors.map((color) => (
                                    <span
                                        key={`${color.hex}-${color.pct}`}
                                        title={`${color.hex} - ${percent(color.pct)} of pixels in this fixed HSV bin`}
                                    >
                                        <i style={{ background: color.hex }} />
                                        {percent(color.pct)}
                                    </span>
                                ))}
                            </div>
                        </DetailSection>

                        <DetailSection label="Similar Paintings">
                            <div className="detail-similar">
                                {similar.map((item) => (
                                    <button
                                        type="button"
                                        key={item.id}
                                        className="similar-row"
                                        onClick={() =>
                                            onInspectPainting(item.id)
                                        }
                                    >
                                        <PaintingImage
                                            src={item.imageUrl}
                                            alt={item.title}
                                        />
                                        <span>
                                            <strong>{item.title}</strong>
                                            <small>
                                                {item.artist}
                                                {item.year
                                                    ? ` - ${item.year}`
                                                    : ""}
                                            </small>
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </DetailSection>
                    </div>
                </div>
            </div>
        </div>
    );
}

function MaybeMeta({ label, value }: { label: string; value: string }) {
    if (!value) {
        return null;
    }
    return (
        <div>
            <span>{label}</span>
            <strong>{value}</strong>
        </div>
    );
}

function DetailSection({
    label,
    children,
}: {
    label: string;
    children: React.ReactNode;
}) {
    return (
        <section className="detail-section">
            <div className="detail-section-label">{label}</div>
            {children}
        </section>
    );
}

function findSimilarPaintings(selected: Painting, paintings: Painting[]) {
    const selectedMotifs = new Set(
        selected.motifs.map((item) => item.toLowerCase()),
    );
    const selectedColors = new Map(
        selected.colors.map((item) => [item.hex, item.pct]),
    );

    return paintings
        .filter((painting) => painting.id !== selected.id)
        .map((painting) => {
            let score = painting.movement === selected.movement ? 1.25 : 0;
            if (selected.embedding && painting.embedding) {
                const dx = selected.embedding.x - painting.embedding.x;
                const dy = selected.embedding.y - painting.embedding.y;
                score += 4 / (1 + Math.sqrt(dx * dx + dy * dy) * 900);
            }
            score += painting.motifs.reduce(
                (total, motif) =>
                    total + (selectedMotifs.has(motif.toLowerCase()) ? 1.1 : 0),
                0,
            );
            score += painting.colors.reduce((total, color) => {
                const selectedPct = selectedColors.get(color.hex);
                return (
                    total +
                    (selectedPct ? Math.min(selectedPct, color.pct) * 9 : 0)
                );
            }, 0);
            return { ...painting, similarityScore: score };
        })
        .filter((painting) => painting.similarityScore > 0)
        .sort((a, b) => b.similarityScore - a.similarityScore);
}

function Presentation({
    data,
    onInspectPainting,
    onExplore,
}: {
    data: ArtData;
    onInspectPainting: (id: string) => void;
    onExplore: () => void;
}) {
    const [activeSlide, setActiveSlide] = useState(0);
    const shellRef = useRef<HTMLDivElement | null>(null);
    const slideRefs = useRef<(HTMLElement | null)[]>([]);

    useEffect(() => {
        const shell = shellRef.current;
        if (!shell) {
            return;
        }
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    const index = slideRefs.current.indexOf(
                        entry.target as HTMLElement,
                    );
                    if (
                        entry.isIntersecting &&
                        entry.intersectionRatio > 0.52 &&
                        index >= 0
                    ) {
                        setActiveSlide(index);
                        entry.target.classList.add("in-view");
                    }
                });
            },
            { root: shell, threshold: [0.52] },
        );
        slideRefs.current.forEach((slide) => slide && observer.observe(slide));
        return () => observer.disconnect();
    }, []);

    const goToSlide = (index: number) => {
        slideRefs.current[index]?.scrollIntoView({ behavior: "smooth" });
    };
    const slideAccents = [
        "#2f5061",
        data.movements[0]?.accent ?? "#7e8f57",
        data.movements[1]?.accent ?? "#9f5138",
        data.movements[3]?.accent ?? "#b9925a",
        data.movements[4]?.accent ?? "#577f78",
        "#2f5061",
    ];

    return (
        <>
            <div className="slide-progress">
                {slides.map((slide, index) => (
                    <button
                        type="button"
                        key={slide}
                        className={`slide-dot ${activeSlide === index ? "active" : ""}`}
                        data-label={slide}
                        style={
                            {
                                "--slide-accent": slideAccents[index],
                            } as React.CSSProperties
                        }
                        onClick={() => goToSlide(index)}
                        aria-label={`Go to ${slide}`}
                    />
                ))}
            </div>
            <main className="present-shell" ref={shellRef}>
                <IntroSlide
                    data={data}
                    refSetter={(node) => (slideRefs.current[0] = node)}
                />
                <MovementSlide
                    data={data}
                    refSetter={(node) => (slideRefs.current[1] = node)}
                    onInspectPainting={onInspectPainting}
                />
                <MotifSlide
                    data={data}
                    refSetter={(node) => (slideRefs.current[2] = node)}
                    onInspectPainting={onInspectPainting}
                />
                <ColorSlide
                    data={data}
                    refSetter={(node) => (slideRefs.current[3] = node)}
                    onInspectPainting={onInspectPainting}
                />
                <EmbeddingSlide
                    data={data}
                    refSetter={(node) => (slideRefs.current[4] = node)}
                    onInspectPainting={onInspectPainting}
                />
                <ClosingSlide
                    refSetter={(node) => (slideRefs.current[5] = node)}
                    onExplore={onExplore}
                    onStartOver={() => goToSlide(0)}
                />
            </main>
        </>
    );
}

function SlideFrame({
    children,
    refSetter,
    className = "",
}: {
    children: React.ReactNode;
    refSetter: (node: HTMLElement | null) => void;
    className?: string;
}) {
    return (
        <section className={`slide ${className}`} ref={refSetter}>
            {children}
        </section>
    );
}

function MethodLabel({ label, note }: { label: string; note: string }) {
    return (
        <span className="method-label">
            <span>{label}</span>
            <span
                className="method-info"
                tabIndex={0}
                aria-label={`${label} method note`}
            >
                <Info size={14} />
                <span className="method-tip">{note}</span>
            </span>
        </span>
    );
}

function IntroSlide({
    data,
    refSetter,
}: {
    data: ArtData;
    refSetter: (node: HTMLElement | null) => void;
}) {
    return (
        <SlideFrame refSetter={refSetter} className="intro-slide">
            <div className="slide-eyebrow slide-content">
                <span className="label">Network Analysis</span>
            </div>
            <h2 className="display slide-title slide-content">
                Network History
                <br />
                of <em>Western Art</em>
            </h2>
            <p className="slide-lede slide-content">
                Five movements. Ten networks. One spectral map.
            </p>
            <ArtworkConstellation data={data} variant="slide" />
        </SlideFrame>
    );
}

function MovementSlide({
    data,
    refSetter,
    onInspectPainting,
}: {
    data: ArtData;
    refSetter: (node: HTMLElement | null) => void;
    onInspectPainting: (id: string) => void;
}) {
    const [activeMovementId, setActiveMovementId] = useState(
        data.movements[0].id,
    );
    const activeMovement =
        data.movements.find((item) => item.id === activeMovementId) ??
        data.movements[0];
    const activeIndex = data.movements.findIndex(
        (item) => item.id === activeMovement.id,
    );

    return (
        <SlideFrame refSetter={refSetter} className="scope-slide">
            <div className="slide-eyebrow stagger-child">
                <span className="label">Five movements</span>
            </div>
            <h2 className="display slide-title stagger-child">
                The <em>five movements</em> in scope.
            </h2>
            <div className="slide-movements stagger-child">
                <div className="movement-list">
                    {data.movements.map((movement, index) => (
                        <button
                            type="button"
                            key={movement.id}
                            className={`movement-row ${activeMovementId === movement.id ? "active" : ""}`}
                            style={
                                {
                                    "--movement-accent": movement.accent,
                                } as React.CSSProperties
                            }
                            onClick={() => setActiveMovementId(movement.id)}
                        >
                            <span className="movement-num">
                                {String(index + 1).padStart(2, "0")}
                            </span>
                            <span className="movement-name">
                                <em>{movement.label}</em>
                            </span>
                            <span className="movement-count">
                                {formatNumber(movement.paintings)}
                            </span>
                        </button>
                    ))}
                </div>
                <div className="movement-stack" aria-live="polite">
                    {data.movements.map((movement, index) => {
                        const featured = data.paintings.find(
                            (item) => item.id === movement.featuredPaintingId,
                        );
                        const rawDistance = index - activeIndex;
                        const distance =
                            rawDistance < 0
                                ? rawDistance + data.movements.length
                                : rawDistance;
                        const isActive = movement.id === activeMovement.id;
                        return (
                            <div
                                key={movement.id}
                                className={`movement-detail ${isActive ? "active" : "stacked"}`}
                                style={
                                    {
                                        "--movement-accent": movement.accent,
                                        "--stack-distance": distance,
                                        "--stack-index":
                                            data.movements.length - distance,
                                    } as React.CSSProperties
                                }
                                onClick={() => setActiveMovementId(movement.id)}
                                aria-pressed={isActive}
                            >
                                <div className="movement-detail-art">
                                    {featured ? (
                                        <button
                                            type="button"
                                            className="movement-art-button"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                onInspectPainting(featured.id);
                                            }}
                                        >
                                            <PaintingImage
                                                src={featured.imageUrl}
                                                alt={featured.title}
                                            />
                                        </button>
                                    ) : (
                                        <div className="image-fallback" />
                                    )}
                                    <span>Popular Work</span>
                                </div>
                                <div className="movement-detail-text">
                                    <div>
                                        <h3>{movement.label}</h3>
                                        <div className="movement-detail-years">
                                            {movement.years}
                                        </div>
                                        <p>{movement.description}</p>
                                    </div>
                                    {featured && (
                                        <div className="featured-caption">
                                            <strong>{featured.title}</strong>
                                            <span>{featured.artist}</span>
                                        </div>
                                    )}
                                    <div className="movement-detail-meta">
                                        <div>
                                            <strong>
                                                {formatNumber(
                                                    movement.paintings,
                                                )}
                                            </strong>
                                            <span>Paintings</span>
                                        </div>
                                        <div>
                                            <strong>
                                                {formatNumber(
                                                    movement.uniqueMotifs,
                                                )}
                                            </strong>
                                            <span>Unique Motifs</span>
                                        </div>
                                        <div>
                                            <strong>
                                                {formatNumber(
                                                    movement.colorEdges,
                                                )}
                                            </strong>
                                            <span>Color Links</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </SlideFrame>
    );
}

function MotifSlide({
    data,
    refSetter,
    onInspectPainting,
}: {
    data: ArtData;
    refSetter: (node: HTMLElement | null) => void;
    onInspectPainting: (id: string) => void;
}) {
    const [movementId, setMovementId] = useState("impressionism");
    const [metric, setMetric] = useState<CentralityMetric>("weightedDegree");
    const [rankingOpen, setRankingOpen] = useState(false);
    const [networkOpen, setNetworkOpen] = useState(false);
    const movement =
        data.movements.find((item) => item.id === movementId) ??
        data.movements[0];
    const rankings = data.analysis.centrality[movementId][metric] ?? [];
    const graph = data.analysis.motifGraphs[movementId];

    return (
        <SlideFrame refSetter={refSetter}>
            <div className="slide-eyebrow stagger-child">
                <MethodLabel
                    label="Motif Centrality"
                    note={methodNotes.motif}
                />
            </div>
            <h2 className="display slide-title stagger-child">
                What each movement <em>is about.</em>
            </h2>
            <div className="motif-mv-tabs stagger-child">
                {data.movements.map((movementItem) => (
                    <button
                        type="button"
                        key={movementItem.id}
                        className={
                            movementId === movementItem.id ? "active" : ""
                        }
                        onClick={() => setMovementId(movementItem.id)}
                    >
                        {movementItem.label}
                    </button>
                ))}
            </div>
            <div className="motif-slide-grid stagger-child">
                <div className="motif-ranking-panel">
                    <div className="vertical-tabs">
                        {centralityTabs.map((tab) => (
                            <button
                                type="button"
                                key={tab.id}
                                className={metric === tab.id ? "active" : ""}
                                onClick={() => setMetric(tab.id)}
                            >
                                {tab.short}
                            </button>
                        ))}
                    </div>
                    <div className="ranking-list">
                        <div className="ranking-head">
                            <span>
                                {
                                    centralityTabs.find(
                                        (tab) => tab.id === metric,
                                    )?.label
                                }
                            </span>
                            <button
                                type="button"
                                onClick={() => setRankingOpen(true)}
                            >
                                <Maximize2 size={15} />
                                Full list
                            </button>
                        </div>
                        {rankings.slice(0, 10).map((item, index) => (
                            <RankRow
                                key={item.id}
                                item={item}
                                metric={metric}
                                index={index}
                            />
                        ))}
                    </div>
                </div>
                <div className="motif-network-wrap">
                    <button
                        type="button"
                        className="corner-action"
                        onClick={() => setNetworkOpen(true)}
                    >
                        <Maximize2 size={15} />
                        Fullscreen
                    </button>
                    <NetworkSvg graph={graph} movement={movement} compact />
                    <div className="motif-network-caption">
                        Louvain Communities - {graph.communities.length}{" "}
                        Communities - {graph.modularity.toFixed(2)} Modularity
                    </div>
                </div>
            </div>
            {rankingOpen && (
                <RankingModal
                    movement={movement}
                    metric={metric}
                    rankings={rankings}
                    onClose={() => setRankingOpen(false)}
                />
            )}
            {networkOpen && (
                <NetworkModal
                    movement={movement}
                    graph={graph}
                    onClose={() => setNetworkOpen(false)}
                    onInspectPainting={onInspectPainting}
                />
            )}
        </SlideFrame>
    );
}

function RankRow({
    item,
    metric,
    index,
}: {
    item: CentralityItem;
    metric: CentralityMetric;
    index: number;
}) {
    const value = item[metric];
    return (
        <div className="rank-row">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{item.label}</strong>
            <em>{centralityValue(value, metric)}</em>
        </div>
    );
}

function RankingModal({
    movement,
    metric,
    rankings,
    onClose,
}: {
    movement: Movement;
    metric: CentralityMetric;
    rankings: CentralityItem[];
    onClose: () => void;
}) {
    return (
        <ModalShell
            title={`${movement.label} - ${centralityTabs.find((tab) => tab.id === metric)?.label}`}
            onClose={onClose}
        >
            <div className="full-ranking-list">
                {rankings.map((item, index) => (
                    <RankRow
                        key={item.id}
                        item={item}
                        metric={metric}
                        index={index}
                    />
                ))}
            </div>
        </ModalShell>
    );
}

function NetworkSvg({
    graph,
    movement,
    compact = false,
    selectedNodeId,
    onNodeClick,
}: {
    graph: MotifGraph;
    movement: Movement;
    compact?: boolean;
    selectedNodeId?: string;
    onNodeClick?: (node: MotifGraphNode) => void;
}) {
    const communityColor = (community: number) =>
        graph.communities.find((item) => item.id === community)?.color ??
        movement.accent;
    const nodeById = useMemo(
        () => new Map(graph.nodes.map((node) => [node.id, node])),
        [graph.nodes],
    );
    const labeledCompactNodes = useMemo(() => {
        const byCommunity = new Map<number, MotifGraphNode[]>();
        graph.nodes.forEach((node) => {
            byCommunity.set(node.community, [
                ...(byCommunity.get(node.community) ?? []),
                node,
            ]);
        });
        const selected = new Set<string>();
        byCommunity.forEach((nodes) => {
            nodes
                .sort((a, b) => b.weightedDegree - a.weightedDegree)
                .slice(0, 3)
                .forEach((node) => selected.add(node.id));
        });
        return selected;
    }, [graph.nodes]);
    const visibleEdges = compact
        ? graph.edges.filter((edge) => edge.weight > 1)
        : graph.edges;
    return (
        <svg
            className={`network-svg ${compact ? "compact" : ""}`}
            viewBox={`0 0 ${graph.width} ${graph.height}`}
            role="img"
        >
            <title>{movement.label} Motif Network</title>
            <g>
                {visibleEdges.map((edge) => {
                    const source = nodeById.get(edge.source);
                    const target = nodeById.get(edge.target);
                    if (!source || !target) {
                        return null;
                    }
                    return (
                        <line
                            key={`${edge.source}-${edge.target}`}
                            x1={source.x}
                            y1={source.y}
                            x2={target.x}
                            y2={target.y}
                            strokeWidth={
                                compact
                                    ? Math.max(0.55, edge.strength * 0.58)
                                    : Math.min(6.4, edge.strength)
                            }
                        />
                    );
                })}
            </g>
            <g className="network-node-layer">
                {graph.nodes.map((node) => (
                    <g
                        key={node.id}
                        className={`network-node ${selectedNodeId === node.id ? "selected" : ""}`}
                        transform={`translate(${node.x}, ${node.y})`}
                        onClick={() => onNodeClick?.(node)}
                    >
                        <title>{node.label}</title>
                        <circle
                            r={
                                compact
                                    ? Math.max(5, node.radius * 0.75)
                                    : node.radius
                            }
                            fill={communityColor(node.community)}
                        />
                    </g>
                ))}
            </g>
            <g className="network-label-layer">
                {graph.nodes.map((node) => {
                    const showLabel =
                        !compact || labeledCompactNodes.has(node.id);
                    if (!showLabel) {
                        return null;
                    }
                    return (
                        <text
                            key={node.id}
                            x={node.x}
                            y={node.y}
                            className={
                                selectedNodeId === node.id ? "selected" : ""
                            }
                            data-long={
                                node.shortLabel.length > 12 ? "true" : undefined
                            }
                        >
                            {node.shortLabel}
                        </text>
                    );
                })}
            </g>
        </svg>
    );
}

function NetworkModal({
    movement,
    graph,
    onClose,
    onInspectPainting,
}: {
    movement: Movement;
    graph: MotifGraph;
    onClose: () => void;
    onInspectPainting: (id: string) => void;
}) {
    const [selectedNode, setSelectedNode] = useState<MotifGraphNode>(
        graph.nodes[0],
    );
    const [selectedExample, setSelectedExample] = useState<
        PaintingExample | undefined
    >(() => randomItem(graph.motifExamples[graph.nodes[0]?.id] ?? []));
    const community = graph.communities.find(
        (item) => item.id === selectedNode.community,
    );
    const examples = graph.motifExamples[selectedNode.id] ?? [];
    const example = selectedExample ?? examples[0];

    const selectNode = (node: MotifGraphNode) => {
        setSelectedNode(node);
        setSelectedExample(randomItem(graph.motifExamples[node.id] ?? []));
    };

    return (
        <ModalShell
            title={`${movement.label} Motif Network`}
            onClose={onClose}
            wide
        >
            <div className="network-fullscreen">
                <div className="network-scroll">
                    <NetworkSvg
                        graph={graph}
                        movement={movement}
                        selectedNodeId={selectedNode.id}
                        onNodeClick={selectNode}
                    />
                </div>
                <aside className="network-inspector" key={selectedNode.id}>
                    <span className="label">Selected motif</span>
                    <h3>{selectedNode.label}</h3>
                    <p>{community?.description}</p>
                    <div className="community-strip">
                        {community?.topMotifs.map((motif) => (
                            <span key={motif}>{motif}</span>
                        ))}
                    </div>
                    {example && (
                        <button
                            type="button"
                            key={example.id}
                            className="motif-example"
                            onClick={() => onInspectPainting(example.id)}
                        >
                            <PaintingImage
                                src={example.imageUrl}
                                alt={example.title}
                            />
                            <strong>{example.title}</strong>
                            <span>{example.artist}</span>
                        </button>
                    )}
                </aside>
            </div>
        </ModalShell>
    );
}

function ColorSlide({
    data,
    refSetter,
    onInspectPainting,
}: {
    data: ArtData;
    refSetter: (node: HTMLElement | null) => void;
    onInspectPainting: (id: string) => void;
}) {
    const defaultExample = useMemo(() => {
        for (const row of data.analysis.colors.rankTable) {
            for (const movement of data.movements) {
                const example = row.cells[movement.id]?.examples[0];
                if (example) {
                    return example;
                }
            }
        }
        return null;
    }, [data]);
    const [activeExample, setActiveExample] = useState<PaintingExample | null>(
        null,
    );
    const [activeCell, setActiveCell] = useState("");
    const [activeAccent, setActiveAccent] = useState<{
        example: PaintingExample;
        label: string;
    } | null>(null);
    const shownExample = activeExample ?? defaultExample;

    const chooseExample = (cell: ColorCell, cellKey: string) => {
        if (!cell.examples.length) {
            setActiveExample(null);
            setActiveCell("");
            return;
        }
        const index = Math.floor(Math.random() * cell.examples.length);
        setActiveExample(cell.examples[index]);
        setActiveCell(cellKey);
        window.setTimeout(() => {
            const panel = document.querySelector(".color-example-panel");
            panel?.classList.add("pulse");
            window.setTimeout(() => panel?.classList.remove("pulse"), 260);
        }, 0);
    };

    const chooseAccentExample = (
        examples: PaintingExample[],
        label: string,
    ) => {
        const example = randomItem(examples);
        if (example) {
            setActiveAccent({ example, label });
        }
    };

    return (
        <SlideFrame refSetter={refSetter}>
            <div className="slide-eyebrow stagger-child">
                <MethodLabel label="Color Rank" note={methodNotes.color} />
            </div>
            <h2 className="display slide-title stagger-child">
                A palette in <em>motion.</em>
            </h2>
            <div className="color-slide-grid stagger-child">
                <div className="color-rank-table">
                    <div className="color-timeline-header">
                        <div>Color</div>
                        {data.movements.map((movement) => (
                            <div key={movement.id}>{movement.shortLabel}</div>
                        ))}
                    </div>
                    {data.analysis.colors.rankTable.map((row) => (
                        <div key={row.hex} className="color-timeline-row">
                            <div className="color-timeline-color">
                                <i style={{ background: row.hex }} />
                                <span title={row.hex}>
                                    {colorName(row.hex)}
                                </span>
                            </div>
                            {data.movements.map((movement) => {
                                const cell = row.cells[movement.id];
                                const cellKey = `${row.hex}-${movement.id}`;
                                return (
                                    <button
                                        type="button"
                                        key={cellKey}
                                        className={`color-rank-cell ${cell.rank && cell.rank <= 3 ? "top" : ""} ${
                                            activeCell === cellKey
                                                ? "selected"
                                                : ""
                                        }`}
                                        onClick={() =>
                                            chooseExample(cell, cellKey)
                                        }
                                        disabled={!cell.examples.length}
                                        title={
                                            cell.examples.length
                                                ? "Show an example painting"
                                                : "No painting example available"
                                        }
                                    >
                                        {cell.rank ? cell.rank : "-"}
                                    </button>
                                );
                            })}
                        </div>
                    ))}
                </div>
                <div className="distinctive-panel">
                    <span className="label">Distinctive accents</span>
                    {data.movements.map((movement) => (
                        <div key={movement.id} className="accent-row">
                            <strong>{movement.shortLabel}</strong>
                            <p>
                                {data.analysis.colors.distinctive[movement.id]
                                    ?.slice(0, 6)
                                    .map((color) => {
                                        return (
                                            <span
                                                key={color.hex}
                                                className="accent-swatch-wrap"
                                                onMouseEnter={() =>
                                                    chooseAccentExample(
                                                        color.examples,
                                                        `${movement.shortLabel} ${color.hex}`,
                                                    )
                                                }
                                                onFocus={() =>
                                                    chooseAccentExample(
                                                        color.examples,
                                                        `${movement.shortLabel} ${color.hex}`,
                                                    )
                                                }
                                                onMouseLeave={() =>
                                                    setActiveAccent(null)
                                                }
                                                onBlur={() =>
                                                    setActiveAccent(null)
                                                }
                                                tabIndex={0}
                                            >
                                                <i
                                                    style={{
                                                        background: color.hex,
                                                    }}
                                                    title={`${color.hex} lift ${color.lift}`}
                                                />
                                            </span>
                                        );
                                    })}
                            </p>
                        </div>
                    ))}
                    <div className="color-example-panel">
                        {shownExample && (
                            <button
                                type="button"
                                key={shownExample.id}
                                onClick={() =>
                                    onInspectPainting(shownExample.id)
                                }
                            >
                                <span className="example-kicker">
                                    Color Rank Example
                                </span>
                                <PaintingImage
                                    src={shownExample.imageUrl}
                                    alt={shownExample.title}
                                />
                                <strong>{shownExample.title}</strong>
                                <span>{shownExample.artist}</span>
                            </button>
                        )}
                    </div>
                </div>
                {activeAccent && (
                    <aside className="color-accent-preview">
                        <button
                            type="button"
                            key={activeAccent.example.id}
                            onClick={() =>
                                onInspectPainting(activeAccent.example.id)
                            }
                        >
                            <span className="example-kicker">
                                {activeAccent.label}
                            </span>
                            <PaintingImage
                                src={activeAccent.example.imageUrl}
                                alt={activeAccent.example.title}
                            />
                            <strong>{activeAccent.example.title}</strong>
                            <small>{activeAccent.example.artist}</small>
                        </button>
                    </aside>
                )}
            </div>
        </SlideFrame>
    );
}

function EmbeddingSlide({
    data,
    refSetter,
    onInspectPainting,
}: {
    data: ArtData;
    refSetter: (node: HTMLElement | null) => void;
    onInspectPainting: (id: string) => void;
}) {
    const [activeMovementId, setActiveMovementId] = useState(
        data.movements[0]?.id ?? "northern_renaissance",
    );
    const [hoveredPaintingId, setHoveredPaintingId] = useState<string | null>(
        null,
    );
    const movementById = useMemo(
        () => new Map(data.movements.map((item) => [item.id, item])),
        [data.movements],
    );
    const paintingsById = useMemo(
        () =>
            new Map(data.paintings.map((painting) => [painting.id, painting])),
        [data.paintings],
    );
    const activeMovement =
        movementById.get(activeMovementId) ?? data.movements[0];
    const activeMedoid = data.analysis.embedding.medoids[activeMovementId];
    const hoveredPainting = hoveredPaintingId
        ? (paintingsById.get(hoveredPaintingId) ?? null)
        : null;
    const previewPainting = hoveredPainting
        ? {
              id: hoveredPainting.id,
              title: hoveredPainting.title,
              artist: hoveredPainting.artist,
              imageUrl: hoveredPainting.imageUrl,
              label: "Hovered Painting",
          }
        : activeMedoid
          ? {
                id: activeMedoid.paintingId,
                title: activeMedoid.title,
                artist: activeMedoid.artist,
                imageUrl: activeMedoid.imageUrl,
                label: "Movement Medoid",
            }
          : null;

    return (
        <SlideFrame refSetter={refSetter}>
            <div className="slide-eyebrow stagger-child">
                <MethodLabel
                    label="Geometric Embedding"
                    note={methodNotes.embedding}
                />
            </div>
            <h2 className="display slide-title stagger-child">
                Movements <em>cluster</em> in space.
            </h2>
            <div className="embedding-grid stagger-child">
                <div className="embedding-tabs" aria-label="Embedding movement">
                    {data.movements.map((movement) => (
                        <button
                            type="button"
                            key={movement.id}
                            className={
                                activeMovementId === movement.id ? "active" : ""
                            }
                            style={
                                {
                                    "--movement-accent": movement.accent,
                                } as React.CSSProperties
                            }
                            onClick={() => {
                                setActiveMovementId(movement.id);
                                setHoveredPaintingId(null);
                            }}
                        >
                            <span>{movement.shortLabel}</span>
                        </button>
                    ))}
                </div>
                <EmbeddingScatter
                    data={data}
                    activeMovementId={activeMovementId}
                    onInspectPainting={onInspectPainting}
                    onHoverPainting={setHoveredPaintingId}
                />
                <aside className="embedding-medoid-panel">
                    <span className="label">{activeMovement.label}</span>
                    <strong>
                        {formatNumber(activeMovement.embeddedPaintings)}
                    </strong>
                    <small>Embedded Paintings</small>
                    <p>{previewPainting?.label ?? "Movement Medoid"}</p>
                    {previewPainting ? (
                        <button
                            type="button"
                            className="embedding-medoid-card"
                            key={previewPainting.id}
                            onClick={() =>
                                onInspectPainting(previewPainting.id)
                            }
                        >
                            <PaintingImage
                                src={previewPainting.imageUrl}
                                alt={previewPainting.title}
                            />
                            <span>{previewPainting.label}</span>
                            <strong>{previewPainting.title}</strong>
                            <small>{previewPainting.artist}</small>
                        </button>
                    ) : null}
                </aside>
            </div>
        </SlideFrame>
    );
}

function EmbeddingScatter({
    data,
    activeMovementId,
    onInspectPainting,
    onHoverPainting,
}: {
    data: ArtData;
    activeMovementId: string;
    onInspectPainting: (id: string) => void;
    onHoverPainting: (id: string | null) => void;
}) {
    const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
    const [plotActive, setPlotActive] = useState(false);
    const plotRef = useRef<HTMLDivElement | null>(null);
    const scatterRef = useRef<SVGSVGElement | null>(null);
    const dragRef = useRef<{
        pointerId: number;
        startX: number;
        startY: number;
        originX: number;
        originY: number;
    } | null>(null);
    const movementById = useMemo(
        () => new Map(data.movements.map((item) => [item.id, item])),
        [data.movements],
    );
    const points = data.analysis.embedding.points;
    const visiblePoints = points.filter(
        (point) => point.movement === activeMovementId,
    );
    const medoidIds = new Set(
        Object.values(data.analysis.embedding.medoids).map(
            (medoid) => medoid.paintingId,
        ),
    );
    const bounds = useMemo(() => {
        const xs = points.map((point) => point.x);
        const ys = points.map((point) => point.y);
        return {
            minX: Math.min(...xs),
            maxX: Math.max(...xs),
            minY: Math.min(...ys),
            maxY: Math.max(...ys),
        };
    }, [points]);
    const width = 640;
    const height = 460;
    const xFor = (point: EmbeddingPoint) =>
        58 +
        ((point.x - bounds.minX) /
            Math.max(bounds.maxX - bounds.minX, 0.00001)) *
            (width - 116);
    const yFor = (point: EmbeddingPoint) =>
        height -
        46 -
        ((point.y - bounds.minY) /
            Math.max(bounds.maxY - bounds.minY, 0.00001)) *
            (height - 92);
    const zoomBy = (factor: number) => {
        setView((current) => ({
            ...current,
            scale: Math.max(1, Math.min(4, current.scale * factor)),
        }));
    };

    useEffect(() => {
        setView({ scale: 1, x: 0, y: 0 });
        onHoverPainting(null);
    }, [activeMovementId, onHoverPainting]);

    useEffect(() => {
        const plot = plotRef.current;
        if (!plot) {
            return undefined;
        }
        const handleWheel = (event: WheelEvent) => {
            event.preventDefault();
            event.stopPropagation();
            setPlotActive(true);
            const svg = scatterRef.current;
            const rect = svg?.getBoundingClientRect();
            setView((current) => ({
                ...current,
                ...(() => {
                    const nextScale = Math.max(
                        1,
                        Math.min(
                            4,
                            current.scale * (event.deltaY < 0 ? 1.1 : 0.9),
                        ),
                    );
                    if (!rect || rect.width === 0 || rect.height === 0) {
                        return { scale: nextScale };
                    }
                    const mouseX =
                        ((event.clientX - rect.left) / rect.width) * width;
                    const mouseY =
                        ((event.clientY - rect.top) / rect.height) * height;
                    const worldX = (mouseX - current.x) / current.scale;
                    const worldY = (mouseY - current.y) / current.scale;
                    return {
                        scale: nextScale,
                        x: mouseX - worldX * nextScale,
                        y: mouseY - worldY * nextScale,
                    };
                })(),
            }));
        };
        plot.addEventListener("wheel", handleWheel, {
            passive: false,
            capture: true,
        });
        return () => plot.removeEventListener("wheel", handleWheel, true);
    }, []);

    return (
        <div
            className={`embedding-plot ${plotActive ? "active" : ""}`}
            ref={plotRef}
            tabIndex={0}
            onFocus={() => setPlotActive(true)}
            onBlur={() => setPlotActive(false)}
            onPointerDown={() => setPlotActive(true)}
            aria-label="Interactive embedding plot. Use the wheel to zoom and drag to pan."
        >
            <div
                className="embedding-zoom-controls"
                aria-label="Embedding zoom controls"
            >
                <button
                    type="button"
                    onClick={() => zoomBy(1.18)}
                    aria-label="Zoom in"
                >
                    +
                </button>
                <button
                    type="button"
                    onClick={() => zoomBy(0.85)}
                    aria-label="Zoom out"
                >
                    -
                </button>
                <button
                    type="button"
                    onClick={() => setView({ scale: 1, x: 0, y: 0 })}
                    aria-label="Reset zoom"
                >
                    Reset
                </button>
            </div>
            <svg
                ref={scatterRef}
                className="embedding-scatter"
                viewBox={`0 0 ${width} ${height}`}
                role="img"
                onPointerDown={(event) => {
                    dragRef.current = {
                        pointerId: event.pointerId,
                        startX: event.clientX,
                        startY: event.clientY,
                        originX: view.x,
                        originY: view.y,
                    };
                    event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                    const drag = dragRef.current;
                    if (!drag || drag.pointerId !== event.pointerId) {
                        return;
                    }
                    setView((current) => ({
                        ...current,
                        x: drag.originX + event.clientX - drag.startX,
                        y: drag.originY + event.clientY - drag.startY,
                    }));
                }}
                onPointerUp={(event) => {
                    if (dragRef.current?.pointerId === event.pointerId) {
                        dragRef.current = null;
                    }
                }}
                onPointerCancel={() => {
                    dragRef.current = null;
                }}
            >
                <title>Laplacian Eigenmap embedding scatter</title>
                <g
                    transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}
                >
                    <line
                        x1="58"
                        x2={width - 58}
                        y1={height / 2}
                        y2={height / 2}
                    />
                    <line
                        x1={width / 2}
                        x2={width / 2}
                        y1="46"
                        y2={height - 46}
                    />
                    {visiblePoints.map((point) => {
                        const movement = movementById.get(point.movement);
                        const medoid = medoidIds.has(point.id);
                        return (
                            <g
                                key={point.id}
                                className={`embedding-point ${medoid ? "embedding-medoid-node" : ""}`}
                                onMouseEnter={() => onHoverPainting(point.id)}
                                onMouseLeave={() => onHoverPainting(null)}
                                onFocus={() => onHoverPainting(point.id)}
                                onBlur={() => onHoverPainting(null)}
                                onClick={
                                    medoid
                                        ? () => onInspectPainting(point.id)
                                        : undefined
                                }
                                role={medoid ? "button" : undefined}
                                tabIndex={medoid ? 0 : undefined}
                                onKeyDown={
                                    medoid
                                        ? (event) => {
                                              if (
                                                  event.key === "Enter" ||
                                                  event.key === " "
                                              ) {
                                                  onInspectPainting(point.id);
                                              }
                                          }
                                        : undefined
                                }
                            >
                                <circle
                                    cx={xFor(point)}
                                    cy={yFor(point)}
                                    r={medoid ? 8.5 : 3.25}
                                    fill={movement?.accent ?? "var(--ink)"}
                                    className={medoid ? "medoid" : ""}
                                />
                            </g>
                        );
                    })}
                </g>
            </svg>
        </div>
    );
}

function ClosingSlide({
    refSetter,
    onExplore,
    onStartOver,
}: {
    refSetter: (node: HTMLElement | null) => void;
    onExplore: () => void;
    onStartOver: () => void;
}) {
    return (
        <SlideFrame refSetter={refSetter} className="slide-closing">
            <div className="slide-eyebrow stagger-child">
                <span className="label">Art History x Network Science</span>
            </div>
            <h2 className="display slide-title stagger-child">
                Art history,
                <br />
                <em>mathematically.</em>
            </h2>
            <div className="closing-actions stagger-child">
                <button
                    type="button"
                    className="btn-primary"
                    onClick={onExplore}
                >
                    <span>Explore the paintings</span>
                    <ArrowRight size={15} />
                </button>
                <button
                    type="button"
                    className="btn-ghost"
                    onClick={onStartOver}
                >
                    <RotateCcw size={15} />
                    Start over
                </button>
            </div>
        </SlideFrame>
    );
}

function ModalShell({
    title,
    children,
    onClose,
    wide = false,
}: {
    title: string;
    children: React.ReactNode;
    onClose: () => void;
    wide?: boolean;
}) {
    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                onClose();
            }
        };
        document.addEventListener("keydown", onKeyDown);
        document.body.classList.add("modal-open");
        return () => {
            document.removeEventListener("keydown", onKeyDown);
            document.body.classList.remove("modal-open");
        };
    }, [onClose]);

    return (
        <div
            className="analysis-modal-backdrop"
            onMouseDown={(event) =>
                event.target === event.currentTarget && onClose()
            }
        >
            <div className={`analysis-modal ${wide ? "wide" : ""}`}>
                <header>
                    <h2>{title}</h2>
                    <button type="button" onClick={onClose}>
                        <X size={18} />
                    </button>
                </header>
                {children}
            </div>
        </div>
    );
}

function PaintingImage({ src, alt }: { src: string; alt: string }) {
    const [failed, setFailed] = useState(false);
    if (!src || failed) {
        return (
            <div className="image-fallback" role="img" aria-label={alt}>
                <span>{alt.slice(0, 1).toUpperCase()}</span>
            </div>
        );
    }
    return (
        <img
            src={src}
            alt={alt}
            loading="lazy"
            decoding="async"
            onError={() => setFailed(true)}
        />
    );
}

export default App;
