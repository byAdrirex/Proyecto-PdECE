import { describe, expect, it } from 'vitest';

import catalogFixture from '../../data/catalog.json';
import objectivesFixture from '../../data/objectives.json';
import { buildMallaModel } from './curriculum';
import { normalizeAttempts } from './kardex';
import { applyObjectiveSelections, electiveProgress } from './objectives';
import type { Catalog, ObjectivesData } from './types';

const catalog = catalogFixture as Catalog;
const objectives = objectivesFixture as ObjectivesData;

describe('applyObjectiveSelections', () => {
  it('integrates active mentions and technicians with stable membership colors', () => {
    const base = buildMallaModel(catalog, normalizeAttempts([]));
    const result = applyObjectiveSelections(base, objectives, {
      mentions: ['M02'],
      technicians: ['T01'],
    });

    expect(result.activeMentions).toEqual(['M02']);
    expect(result.activeTechnicians).toEqual(['T01']);
    expect(result.integrated['1304063']?.memberships.map(({ id }) => id)).toEqual(['M02', 'T01']);
    expect(result.integrated['1304063']?.colorGradient).toBe(
      'linear-gradient(90deg, #f2c7a6 0% 50%, #a8ddd7 50% 100%)',
    );
  });

  it('applies mention substitutions without mutating the base model', () => {
    const base = buildMallaModel(catalog, normalizeAttempts([]));
    const result = applyObjectiveSelections(base, objectives, {
      mentions: ['M03'],
      technicians: [],
    });

    expect(result.substitutions).toEqual({
      '1304022': '1304160',
      '1304028': '1301031',
      '1304033': '1304159',
      '1304035': '1301034',
    });
    expect(result.cells.flatMap(({ subjects }) => subjects).some(({ code }) => code === '1304022')).toBe(false);
    expect(base.cells.flatMap(({ subjects }) => subjects).some(({ code }) => code === '1304022')).toBe(true);
    expect(result.integrated['1304160']?.replaces).toEqual([
      { code: '1304022', name: 'ECONOMIA POLITICA I' },
    ]);
  });
});

describe('electiveProgress', () => {
  it('counts approved trajectory electives against the licenciatura requirement', () => {
    const kardex = normalizeAttempts({
      subjects: [
        { code: '1304160', attempts: [{ result: 'APR' }] },
        { code: '1304134', attempts: [{ result: 'APR' }] },
      ],
    });

    expect(electiveProgress(catalog, kardex, objectives)).toEqual(expect.objectContaining({
      required: 8,
      approved: ['1304134', '1304160'],
      remaining: 6,
      completed: false,
    }));
  });
});
