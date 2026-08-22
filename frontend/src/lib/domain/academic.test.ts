import { describe, expect, it } from 'vitest';

import catalogFixture from '../../data/catalog.json';
import goldenKardex from '../../data/golden-kardex.json';
import goldenResults from '../../data/golden-results.json';
import objectivesFixture from '../../data/objectives.json';
import offerFixture from '../../data/offer.json';
import { normalizeAttempts } from './kardex';
import { progressSummary, subjectState } from './academic';
import type { Catalog, ObjectivesData, Offer } from './types';

const catalog = catalogFixture as Catalog;
const offer = offerFixture as Offer;
const objectives = objectivesFixture as ObjectivesData;
const kardex = normalizeAttempts(goldenKardex);

describe('subjectState', () => {
  it('blocks a subject and lists only unapproved prerequisites', () => {
    const result = subjectState('1304007', catalog, normalizeAttempts({
      subjects: [{ code: '1304001', attempts: [{ result: 'APR' }] }],
    }), offer);

    expect(result.status).toBe('BLOQUEADA');
    expect(result.missingPrerequisites).toEqual(['1304004']);
    expect(result.offered).toBe(true);
  });

  it('makes a subject available once every prerequisite is approved', () => {
    const result = subjectState('1304007', catalog, normalizeAttempts({
      subjects: [
        { code: '1304001', attempts: [{ result: 'APR' }] },
        { code: '1304004', attempts: [{ result: 'APR' }] },
      ],
    }), offer);

    expect(result.status).toBe('DISPONIBLE');
    expect(result.missingPrerequisites).toEqual([]);
  });

  it('separates academic and offer states', () => {
    const result = subjectState('TI01', catalog, kardex, offer);

    expect(result.status).toBe('SIN_PRERREQUISITOS');
    expect(result.offerStatus).toBe('NO_OFERTADA');
    expect(result.groups).toEqual([]);
  });

  it.each(Object.entries(goldenResults.representativeSubjects))(
    'matches the Python oracle for %s',
    (code, expected) => {
      const result = subjectState(code, catalog, kardex, offer);
      expect(result.kardexStatus).toBe(expected.kardexStatus);
      expect(result.offered).toBe(expected.offered);
      expect(result.groups).toHaveLength(expected.groupCount);
    },
  );
});

describe('progressSummary', () => {
  it('reports representative subject and credit totals from fixtures', () => {
    const result = progressSummary(catalog, kardex, objectives, ['M01', 'T01']);

    expect(result.required).toEqual(expect.objectContaining({
      total: 39,
      approved: 24,
      percentage: 61.5,
      credits: 89,
      approvedCredits: 49,
    }));
    expect(result.nonCurricular).toEqual(expect.objectContaining({
      total: 7,
      approved: 2,
      percentage: 28.6,
    }));
    expect(result.totalCredits).toBe(174);
    expect(result.approvedCredits).toBe(55);
    expect(result.mentions.M01?.total).toBe(9);
    expect(result.technicians.T01?.total).toBe(6);
  });
});
