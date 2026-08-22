import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CatalogEdge } from '../lib/domain/types';

const END_PADDING = 16;

interface CardPosition {
  code: string;
  right: number;
  left: number;
  centerY: number;
}

interface GridDimensions {
  width: number;
  height: number;
}

interface DrawnLine extends CatalogEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  curveX: number;
}

function measureCards(gridEl: HTMLElement | null): CardPosition[] {
  if (!gridEl) return [];
  const gridRect = gridEl.getBoundingClientRect();
  const cards = gridEl.querySelectorAll<HTMLElement>('[data-subject-code]');
  return [...cards].map((card) => {
    const rect = card.getBoundingClientRect();
    return {
      code: card.dataset.subjectCode!,
      right: rect.right - gridRect.left,
      left: rect.left - gridRect.left,
      centerY: (rect.top + rect.bottom) / 2 - gridRect.top,
    };
  });
}

function computeGridDimensions(gridEl: HTMLElement | null): GridDimensions {
  if (!gridEl) return { width: 0, height: 0 };
  const rect = gridEl.getBoundingClientRect();
  return { width: rect.width, height: rect.height };
}

interface MallaConnectionsProps {
  connections: CatalogEdge[];
  activeCode: string | null;
}

function MallaConnectionsInner({
  connections,
  activeCode,
  gridWidth,
  gridHeight,
  cardPositions,
}: MallaConnectionsProps & {
  gridWidth: number;
  gridHeight: number;
  cardPositions: CardPosition[];
}) {
  const byCode = useMemo(() => {
    const map = new Map<string, CardPosition>();
    for (const pos of cardPositions) map.set(pos.code, pos);
    return map;
  }, [cardPositions]);

  const drawn = useMemo(() => {
    if (!activeCode) return [];
    const activeCard = byCode.get(activeCode);
    if (!activeCard) return [];

    const activeConnections = connections.filter(
      ({ from, to }) => from === activeCode || to === activeCode,
    );

    return activeConnections
      .map((connection) => {
        const isPrereq = connection.from === activeCode;
        const otherCode = isPrereq ? connection.to : connection.from;
        const otherCard = byCode.get(otherCode);
        if (!otherCard) return null;

        // Original style: arrow from right edge of prereq → left edge of dependent
        let x1: number, y1: number, x2: number, y2: number;
        if (isPrereq) {
          // active is prereq → draw FROM active (right) TO other (left)
          x1 = activeCard.right + 2;
          y1 = activeCard.centerY;
          x2 = otherCard.left - 2;
          y2 = otherCard.centerY;
        } else {
          // active is dependent → draw FROM other (right) TO active (left)
          x1 = otherCard.right + 2;
          y1 = otherCard.centerY;
          x2 = activeCard.left - 2;
          y2 = activeCard.centerY;
        }
        const curveX = (x1 + x2) / 2;

        return { ...connection, x1, y1, x2, y2, curveX };
      })
      .filter((line): line is DrawnLine => line !== null);
  }, [connections, activeCode, byCode]);

  if (drawn.length === 0) return null;

  return (
    <svg
      className="malla-connections-svg"
      viewBox={`0 0 ${gridWidth + END_PADDING} ${gridHeight}`}
      width={gridWidth + END_PADDING}
      height={gridHeight}
      aria-hidden="true"
    >
      <defs>
        <marker
          id="malla-flecha"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#7c3aed" />
        </marker>
      </defs>
      {drawn.map((line) => (
        <path
          key={`${line.from}-${line.to}`}
          d={`M ${line.x1} ${line.y1} C ${line.curveX} ${line.y1}, ${line.curveX} ${line.y2}, ${line.x2} ${line.y2}`}
          fill="none"
          stroke="#7c3aed"
          strokeWidth="2"
          markerEnd="url(#malla-flecha)"
          className="malla-connection-path"
        />
      ))}
    </svg>
  );
}

export function MallaConnections({ connections, activeCode }: MallaConnectionsProps) {
  const scrollRef = useRef<HTMLElement | null>(null);
  const [gridWidth, setGridWidth] = useState(0);
  const [gridHeight, setGridHeight] = useState(0);
  const [cardPositions, setCardPositions] = useState<CardPosition[]>([]);

  const measure = useCallback(() => {
    const grid = scrollRef.current?.querySelector<HTMLElement>('.semester-grid') ?? null;
    const positions = measureCards(grid);
    const dimensions = computeGridDimensions(grid);
    setCardPositions(positions);
    setGridWidth(dimensions.width);
    setGridHeight(dimensions.height);
  }, []);

  useLayoutEffect(() => {
    const scroll = document.querySelector<HTMLElement>('.semester-scroll');
    scrollRef.current = scroll;
    measure();
  }, [measure]);

  useEffect(() => {
    const scroll = scrollRef.current;
    if (!scroll) return;

    const grid = scroll.querySelector<HTMLElement>('.semester-grid');
    if (!grid) return;

    let raf = 0;
    const onFrame = () => {
      measure();
      raf = 0;
    };
    const scheduleMeasure = () => {
      if (!raf) raf = requestAnimationFrame(onFrame);
    };

    const onScroll = () => scheduleMeasure();
    const onResize = () => scheduleMeasure();

    scroll.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onResize);

    const ResizeObserverCtor = typeof ResizeObserver !== 'undefined' ? ResizeObserver : null;
    const observer = ResizeObserverCtor ? new ResizeObserverCtor(scheduleMeasure) : null;
    if (observer) observer.observe(grid);

    measure();

    return () => {
      cancelAnimationFrame(raf);
      scroll.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
      observer?.disconnect();
    };
  }, [measure]);

  if (gridWidth === 0 || cardPositions.length === 0) return null;

  return (
    <MallaConnectionsInner
      connections={connections}
      activeCode={activeCode}
      gridWidth={gridWidth}
      gridHeight={gridHeight}
      cardPositions={cardPositions}
    />
  );
}
