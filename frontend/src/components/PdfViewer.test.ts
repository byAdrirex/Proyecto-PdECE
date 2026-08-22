import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PdfViewer } from './PdfViewer';
import { renderComponent, tick, type RenderedComponent } from './test-utils';

vi.mock('../lib/pdf/pdf-worker', () => ({
  getDocument: vi.fn().mockRejectedValue(new Error('PDF ausente')),
}));

let rendered: RenderedComponent | null = null;

afterEach(async () => {
  await rendered?.cleanup();
  rendered = null;
});

describe('PdfViewer fallback', () => {
  it('links to an official actionable destination instead of the missing local asset', async () => {
    rendered = await renderComponent(createElement(PdfViewer, {
      src: '/calendario-academico.pdf',
      fallbackHref: 'https://www.fce.umss.edu.bo/webpage/',
    }));
    await tick();

    const link = rendered.container.querySelector<HTMLAnchorElement>('a[target="_blank"]');
    expect(link?.href).toBe('https://www.fce.umss.edu.bo/webpage/');
    expect(link?.textContent).toContain('Consultar el calendario en el sitio oficial');
    expect(link?.href).not.toContain('/calendario-academico.pdf');
  });
});
