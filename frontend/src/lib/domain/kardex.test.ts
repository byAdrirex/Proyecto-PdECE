import { describe, expect, it } from 'vitest';

import { determineAttemptState, normalizeAttempts } from './kardex';

describe('normalizeAttempts', () => {
  it('normalizes row aliases while preserving grades, period and mode', () => {
    const result = normalizeAttempts([
      {
        codigo: ' 1304001 ',
        anio: '2026',
        gestion: '3',
        nfin: '67.5',
        rfin: ' apr ',
        md: 'e',
        t1: '60',
      },
    ]);

    expect(result.attempts['1304001']).toEqual([
      expect.objectContaining({
        year: 2026,
        term: 3,
        final: 67.5,
        result: 'APR',
        mode: 'E',
        modality: 'Mesa',
        period: 'intersemestral verano',
        t1: 60,
      }),
    ]);
  });

  it('accepts the sanitized fixture subject shape', () => {
    const result = normalizeAttempts({
      subjects: [{ code: '1304002', attempts: [{ result: 'APR' }] }],
    });

    expect(result.attempts['1304002']?.[0]?.result).toBe('APR');
  });
});

describe('determineAttemptState', () => {
  it.each([
    [51, 'APROBADA'],
    [100, 'APROBADA'],
    [50, 'REPROBADA'],
    [0, 'REPROBADA'],
  ] as const)('classifies final grade %s as %s', (final, status) => {
    expect(determineAttemptState([{ final }]).status).toBe(status);
  });

  it('uses the latest attempt when no attempt was approved', () => {
    const result = determineAttemptState([
      { year: 2026, term: 1, final: 40, result: 'REP' },
      { year: 2025, term: 2, result: 'ABA' },
    ]);

    expect(result.status).toBe('REPROBADA');
    expect(result.latest?.year).toBe(2026);
  });

  it('keeps the first record when attempts share the same year and term', () => {
    const result = determineAttemptState([
      { year: 2026, term: 1, final: 40, result: 'REP' },
      { year: 2026, term: 1, result: 'ABA' },
    ]);

    expect(result.status).toBe('REPROBADA');
    expect(result.latest?.result).toBe('REP');
  });

  it('marks an unfinished current-period attempt as in progress', () => {
    const result = determineAttemptState(
      [{ year: 2026, term: 2 }],
      { year: 2026, term: 2 },
    );

    expect(result).toEqual(expect.objectContaining({
      status: 'EN_CURSO',
      approved: false,
      provisional: true,
    }));
  });

  it('marks a failed current-period result as provisional', () => {
    const result = determineAttemptState(
      [{ year: 2026, term: 2, final: 40, result: 'REP' }],
      { year: 2026, term: 2 },
    );

    expect(result).toEqual(expect.objectContaining({
      status: 'REPROBADA',
      provisional: true,
    }));
  });

  it('keeps a historical approval after a later failure', () => {
    const result = determineAttemptState([
      { year: 2025, term: 1, final: 65, result: 'APR' },
      { year: 2026, term: 1, final: 40, result: 'REP' },
    ]);

    expect(result.status).toBe('APROBADA');
    expect(result.approved).toBe(true);
    expect(result.provisional).toBe(false);
  });
});
