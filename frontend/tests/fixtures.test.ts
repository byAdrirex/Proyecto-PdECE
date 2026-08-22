import catalog from '../src/data/catalog.json';
import goldenKardex from '../src/data/golden-kardex.json';
import offer from '../src/data/offer.json';
import golden from '../src/data/golden-results.json';
import { describe, expect, it } from 'vitest';

describe('academic fixtures', () => {
  it('contains the official curriculum and offer', () => {
    expect(catalog.subjects.length).toBeGreaterThan(0);
    expect(offer.totalSubjects).toBe(70);
    expect(offer.totalGroups).toBe(146);
  });

  it('records the Python oracle counts', () => {
    expect(golden.kardex.approved).toBe(26);
    expect(golden.offer.subjects).toBe(70);
    expect(golden.offer.groups).toBe(146);
  });

  it('keeps only catalogued Kardex subjects', () => {
    expect(goldenKardex.subjectCount).toBe(26);
    expect(goldenKardex.subjects.every((subject) => subject.code !== 'nan')).toBe(true);
  });
});
