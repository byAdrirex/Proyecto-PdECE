import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createElement } from 'react';
import { MallaConnections } from './MallaConnections';
import { renderComponent, type RenderedComponent } from './test-utils';
import catalogFixture from '../data/catalog.json';
import type { Catalog } from '../lib/domain/types';

const catalog = catalogFixture as Catalog;

const edgeSample = catalog.edges[0]!; // 1304023 → 1301031

let rendered: RenderedComponent | null = null;
let scrollEl: HTMLDivElement | null = null;

beforeEach(() => {
  scrollEl = document.createElement('div');
  scrollEl.className = 'semester-scroll';
  const grid = document.createElement('div');
  grid.className = 'semester-grid';

  const codes = new Set<string>();
  for (const edge of catalog.edges) {
    codes.add(edge.from);
    codes.add(edge.to);
  }
  for (const code of codes) {
    const card = document.createElement('button');
    card.dataset.subjectCode = code;
    card.textContent = code;
    grid.appendChild(card);
  }
  scrollEl.appendChild(grid);
  document.body.appendChild(scrollEl);
});

afterEach(async () => {
  await rendered?.cleanup();
  rendered = null;
  if (scrollEl) {
    scrollEl.remove();
    scrollEl = null;
  }
  localStorage.clear();
});

describe('MallaConnections', () => {
  it('renders nothing when no subject is active', async () => {
    rendered = await renderComponent(
      createElement(MallaConnections, {
        connections: [edgeSample],
        activeCode: null,
      }),
    );

    const svg = rendered.container.querySelector('svg.malla-connections-svg');
    expect(svg).toBeNull();
  });

  it('renders SVG overlay when a subject is hovered', async () => {
    rendered = await renderComponent(
      createElement(MallaConnections, {
        connections: [edgeSample],
        activeCode: edgeSample.from,
      }),
    );

    const svg = rendered.container.querySelector('svg.malla-connections-svg');
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute('aria-hidden')).toBe('true');
  });

  it('draws curved paths for active subject connections', async () => {
    rendered = await renderComponent(
      createElement(MallaConnections, {
        connections: catalog.edges,
        activeCode: '1304001',
      }),
    );

    const paths = rendered.container.querySelectorAll('path.malla-connection-path');
    // 1304001 has 3 direct edges: 1304001→1304007, 1304001→1304008, 1304001→1304210
    expect(paths.length).toBe(3);
  });

  it('clears lines when activeCode becomes null', async () => {
    rendered = await renderComponent(
      createElement(MallaConnections, {
        connections: catalog.edges,
        activeCode: '1304001',
      }),
    );

    const pathsBefore = rendered.container.querySelectorAll('path.malla-connection-path');
    expect(pathsBefore.length).toBeGreaterThan(0);

    await rendered.cleanup();
    rendered = await renderComponent(
      createElement(MallaConnections, {
        connections: catalog.edges,
        activeCode: null,
      }),
    );

    const svg = rendered.container.querySelector('svg.malla-connections-svg');
    expect(svg).toBeNull();
  });
});
