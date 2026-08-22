import { subjectState } from './academic';
import type {
  Catalog,
  KardexState,
  MallaCell,
  MallaModel,
  MallaSubject,
  Offer,
  Subject,
} from './types';

export const OFFICIAL_AREAS = [
  'Teoria Economica y Aplicada',
  'Cuantitativa',
  'Historia y Apoyo',
  'Tecnicas y Metodos de Investigacion',
] as const;

export const LEVEL_LABELS: Record<string, string> = {
  A: '1°',
  B: '2°',
  C: '3°',
  D: '4°',
  E: '5°',
  F: '6°',
  G: '7°',
  H: '8°',
  I: '9°',
};

const displayArea = (area: string): string => ({
  e: 'Teoria Economica y Aplicada',
  'Histotia y Apoyo': 'Historia y Apoyo',
})[area] ?? area;

const toMallaSubject = (
  subject: Subject,
  catalog: Catalog,
  kardex: KardexState,
  offer?: Offer | null,
): MallaSubject => {
  const academic = subjectState(subject.code, catalog, kardex, offer);
  return {
    ...subject,
    areaRaw: subject.area,
    area: displayArea(subject.area),
    prerequisites: [...subject.prerequisites],
    dependents: [...subject.dependents],
    status: academic.status,
    missingPrerequisites: academic.missingPrerequisites,
    provisional: academic.provisional,
    offered: academic.offered,
    groupCount: academic.groups.length,
    memberships: [],
  };
};

export function buildMallaModel(
  catalog: Catalog,
  kardex: KardexState,
  offer?: Offer | null,
): MallaModel {
  const subjects = Object.fromEntries(
    catalog.subjects.map((subject) => [subject.code, toMallaSubject(subject, catalog, kardex, offer)]),
  );
  const cells: MallaCell[] = [];

  for (const level of catalog.levels) {
    for (const area of OFFICIAL_AREAS) {
      const cellSubjects = Object.values(subjects)
        .filter((subject) => subject.type === 'Obligatoria' && subject.level === level && subject.area === area)
        .sort((left, right) => left.name.localeCompare(right.name, 'es'));
      if (cellSubjects.length > 0) cells.push({ level, area, subjects: cellSubjects });
    }
  }

  const nonCurricular = Object.values(subjects)
    .filter((subject) => subject.type === 'Obligatoria No Curricular');
  const workshops = nonCurricular
    .filter((subject) => subject.code.toUpperCase().startsWith('TI'))
    .sort((left, right) => left.code.localeCompare(right.code));
  const english = nonCurricular
    .filter((subject) => !subject.code.toUpperCase().startsWith('TI'))
    .sort((left, right) => (left.level ?? '').localeCompare(right.level ?? '') || left.code.localeCompare(right.code));

  return {
    subjects,
    levels: [...catalog.levels],
    levelLabels: { ...LEVEL_LABELS },
    areas: [...OFFICIAL_AREAS],
    cells,
    workshops,
    english,
    connections: catalog.edges.map((edge) => ({ ...edge })),
    totalSubjects: catalog.subjects.length,
    totalRequired: cells.reduce((total, cell) => total + cell.subjects.length, 0),
    activeMentions: [],
    activeTechnicians: [],
    substitutions: {},
    integrated: {},
    integratedByLevel: {},
  };
}
