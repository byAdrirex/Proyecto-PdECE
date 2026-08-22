import { describe, expect, it } from 'vitest';

import catalogFixture from '../../data/catalog.json';
import goldenKardex from '../../data/golden-kardex.json';
import offerFixture from '../../data/offer.json';
import { normalizeAttempts } from './kardex';
import { buildMallaModel } from './curriculum';
import type { Catalog, Offer } from './types';

const catalog = catalogFixture as Catalog;
const offer = offerFixture as Offer;

describe('buildMallaModel', () => {
  it('builds the official semester-by-area cells', () => {
    const model = buildMallaModel(catalog, normalizeAttempts(goldenKardex), offer);
    const firstTheoryCell = model.cells.find(
      (cell) => cell.level === 'A' && cell.area === 'Teoria Economica y Aplicada',
    );

    expect(model.levels).toEqual(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']);
    expect(model.areas).toEqual([
      'Teoria Economica y Aplicada',
      'Cuantitativa',
      'Historia y Apoyo',
      'Tecnicas y Metodos de Investigacion',
    ]);
    expect(firstTheoryCell?.subjects.map((subject) => subject.code)).toEqual(['1304001']);
    expect(model.totalSubjects).toBe(76);
    expect(model.totalRequired).toBe(39);
  });

  it('separates workshops and English requirements', () => {
    const model = buildMallaModel(catalog, normalizeAttempts([]), offer);

    expect(model.workshops.map((subject) => subject.code)).toEqual(['TI01', 'TI02', 'TI03', 'TI04']);
    expect(model.english.map((subject) => subject.code)).toEqual(['1803021', '1803024', '1803027']);
  });

  it('preserves prerequisite dependents and derived state', () => {
    const model = buildMallaModel(catalog, normalizeAttempts(goldenKardex), offer);

    expect(model.subjects['1304001']?.dependents).toEqual(['1304007', '1304008', '1304210']);
    expect(model.subjects['1304001']).toEqual(expect.objectContaining({
      status: 'APROBADA',
      offered: true,
      groupCount: 3,
    }));
  });
});
