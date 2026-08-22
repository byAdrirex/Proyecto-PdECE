import { stateForCode } from './kardex';
import { electiveProgress } from './objectives';
import type {
  AcademicState,
  Catalog,
  KardexState,
  ObjectivesData,
  Offer,
  ProgressCategory,
  ProgressSummary,
  Subject,
} from './types';

const roundOne = (value: number): number => Math.round(value * 10) / 10;

export function subjectState(
  code: string,
  catalog: Catalog,
  kardex: KardexState,
  offer?: Offer | null,
): AcademicState {
  const normalizedCode = String(code);
  const subject = catalog.subjects.find((candidate) => candidate.code === normalizedCode);
  const kardexState = stateForCode(normalizedCode, kardex);
  let status: AcademicState['status'];
  let missingPrerequisites: string[] = [];

  if (kardexState.status !== 'SIN_HISTORIAL') {
    status = kardexState.status;
  } else if (!subject || subject.prerequisites.length === 0) {
    status = 'SIN_PRERREQUISITOS';
  } else {
    missingPrerequisites = subject.prerequisites.filter(
      (prerequisite) => !stateForCode(prerequisite, kardex).approved,
    );
    status = missingPrerequisites.length === 0 ? 'DISPONIBLE' : 'BLOQUEADA';
  }

  const groups = offer?.groupsBySubject[normalizedCode] ?? [];
  const offered = offer == null ? null : groups.length > 0;

  return {
    code: normalizedCode,
    status,
    kardexStatus: kardexState.status,
    provisional: kardexState.provisional,
    missingPrerequisites,
    offered,
    offerStatus: offered == null ? null : offered ? 'OFERTADA' : 'NO_OFERTADA',
    groups,
  };
}

export function progressForSubjects(
  subjects: readonly Subject[],
  kardex: KardexState,
): ProgressCategory {
  const approvedCodes: string[] = [];
  const inProgressCodes: string[] = [];
  const pendingCodes: string[] = [];
  let credits = 0;
  let approvedCredits = 0;

  for (const subject of subjects) {
    const state = stateForCode(subject.code, kardex);
    const subjectCredits = subject.credits ?? 0;
    credits += subjectCredits;
    if (state.approved) {
      approvedCodes.push(subject.code);
      approvedCredits += subjectCredits;
    } else if (state.status === 'EN_CURSO') {
      inProgressCodes.push(subject.code);
    } else {
      pendingCodes.push(subject.code);
    }
  }

  return {
    total: subjects.length,
    approved: approvedCodes.length,
    inProgress: inProgressCodes.length,
    pending: pendingCodes.length,
    percentage: subjects.length === 0 ? 0 : roundOne((approvedCodes.length / subjects.length) * 100),
    credits,
    approvedCredits,
    approvedCodes,
    inProgressCodes,
    pendingCodes,
  };
}

export function progressSummary(
  catalog: Catalog,
  kardex: KardexState,
  objectives: ObjectivesData,
  selectedObjectives: readonly string[] = [],
): ProgressSummary {
  const byCode = new Map(catalog.subjects.map((subject) => [subject.code, subject]));
  const selected = new Set(selectedObjectives.map(String));
  const mentions: Record<string, ProgressCategory> = {};
  const technicians: Record<string, ProgressCategory> = {};

  for (const objective of objectives.mentions) {
    if (!selected.has(objective.id)) continue;
    mentions[objective.id] = progressForSubjects(
      objective.subjectCodes.flatMap((code) => byCode.get(code) ?? []),
      kardex,
    );
  }
  for (const objective of objectives.technicians) {
    if (!selected.has(objective.id)) continue;
    technicians[objective.id] = progressForSubjects(
      objective.subjectCodes.flatMap((code) => byCode.get(code) ?? []),
      kardex,
    );
  }

  return {
    required: progressForSubjects(
      catalog.subjects.filter((subject) => subject.type === 'Obligatoria'),
      kardex,
    ),
    nonCurricular: progressForSubjects(
      catalog.subjects.filter((subject) => subject.type === 'Obligatoria No Curricular'),
      kardex,
    ),
    electives: electiveProgress(catalog, kardex, objectives),
    mentions,
    technicians,
    totalCredits: catalog.subjects.reduce((total, subject) => total + (subject.credits ?? 0), 0),
    approvedCredits: catalog.subjects.reduce(
      (total, subject) => total + (stateForCode(subject.code, kardex).approved ? subject.credits ?? 0 : 0),
      0,
    ),
  };
}
