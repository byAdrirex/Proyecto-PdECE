// @vitest-environment node

import { expect, it, vi } from 'vitest';

it('imports safely during SSR without evaluating browser-only PDF.js', async () => {
  vi.resetModules();

  await expect(import('./kardex-parser')).resolves.toHaveProperty('parseKardexPdf');
});
