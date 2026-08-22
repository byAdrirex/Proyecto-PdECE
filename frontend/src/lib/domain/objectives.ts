import { stateForCode } from './kardex';
import type {
  Catalog,
  ElectiveProgress,
  KardexState,
  MallaModel,
  MallaSubject,
  Objective,
  ObjectiveMembership,
  ObjectivesData,
} from './types';

const OBJECTIVE_COLORS = {
  T01: '#a8ddd7',
  T02: '#e4c1e4',
  T03: '#d7e6b2',
  M01: '#b5dfe6',
  M02: '#f2c7a6',
  M03: '#c6c9e8',
} as const;

const unique = (values: readonly string[]): string[] => [...new Set(values.map(String).filter(Boolean))];

const cloneSubject = (subject: MallaSubject): MallaSubject => ({
  ...subject,
  prerequisites: [...subject.prerequisites],
  dependents: [...subject.dependents],
  missingPrerequisites: [...subject.missingPrerequisites],
  memberships: subject.memberships.map((membership) => ({ ...membership })),
  ...(subject.replaces ? { replaces: subject.replaces.map((item) => ({ ...item })) } : {}),
});

const colorFor = (objective: Objective): string =>
  OBJECTIVE_COLORS[objective.id as keyof typeof OBJECTIVE_COLORS] ?? '#d1d5db';

const percentage = (value: number): string => Number.isInteger(value)
  ? String(value)
  : String(Math.round(value * 1000) / 1000);

const gradientFor = (memberships: readonly ObjectiveMembership[]): string => {
  const width = 100 / memberships.length;
  const stops = memberships.map((membership, index) =>
    `${membership.color} ${percentage(index * width)}% ${percentage((index + 1) * width)}%`,
  );
  return `linear-gradient(90deg, ${stops.join(', ')})`;
};

export interface ObjectiveSelections {
  mentions: readonly string[];
  technicians: readonly string[];
}

export function applyObjectiveSelections(
  model: MallaModel,
  objectives: ObjectivesData,
  selections: ObjectiveSelections,
): MallaModel {
  const subjects = Object.fromEntries(
    Object.entries(model.subjects).map(([code, subject]) => [code, cloneSubject(subject)]),
  );
  const activeMentions = unique(selections.mentions);
  const activeTechnicians = unique(selections.technicians);
  const activeMentionSet = new Set(activeMentions);
  const activeTechnicianSet = new Set(activeTechnicians);
  const selected = [
    ...objectives.mentions.filter((objective) => activeMentionSet.has(objective.id)),
    ...objectives.technicians.filter((objective) => activeTechnicianSet.has(objective.id)),
  ];
  const integrated: Record<string, MallaSubject> = {};

  for (const objective of selected) {
    const membership: ObjectiveMembership = {
      id: objective.id,
      kind: objective.kind,
      name: objective.name,
      color: colorFor(objective),
    };
    for (const code of objective.subjectCodes) {
      const subject = subjects[code];
      if (!subject) continue;
      const integratedSubject = integrated[code] ??= cloneSubject(subject);
      if (!integratedSubject.memberships.some(({ id, kind }) => id === membership.id && kind === membership.kind)) {
        integratedSubject.memberships.push({ ...membership });
      }
    }
  }

  const substitutions = Object.fromEntries(
    objectives.substitutions
      .filter((substitution) => activeMentionSet.has(substitution.mentionId))
      .map((substitution) => [substitution.original, substitution.replacement]),
  );

  for (const [original, replacement] of Object.entries(substitutions)) {
    const originalSubject = subjects[original];
    const replacementSubject = subjects[replacement];
    if (!originalSubject || !replacementSubject) continue;
    const reference = { code: original, name: originalSubject.name };
    (replacementSubject.replaces ??= []).push(reference);
    if (integrated[replacement]) (integrated[replacement].replaces ??= []).push({ ...reference });
  }

  for (const subject of Object.values(integrated)) {
    subject.colorGradient = gradientFor(subject.memberships);
  }

  const cells = model.cells.map((cell) => ({
    ...cell,
    subjects: cell.subjects
      .filter((subject) => !(subject.code in substitutions))
      .map((subject) => subjects[subject.code]!),
  }));
  const integratedByLevel: Record<string, MallaSubject[]> = {};
  for (const subject of Object.values(integrated)) {
    if (!subject.level) continue;
    (integratedByLevel[subject.level] ??= []).push(subject);
  }
  for (const levelSubjects of Object.values(integratedByLevel)) {
    levelSubjects.sort((left, right) => left.name.localeCompare(right.name, 'es'));
  }

  return {
    ...model,
    subjects,
    cells,
    workshops: model.workshops.map((subject) => subjects[subject.code]!),
    english: model.english.map((subject) => subjects[subject.code]!),
    connections: model.connections.map((connection) => ({ ...connection })),
    activeMentions,
    activeTechnicians,
    substitutions,
    integrated,
    integratedByLevel,
  };
}

export function electiveProgress(
  catalog: Catalog,
  kardex: KardexState,
  objectives: ObjectivesData,
): ElectiveProgress {
  const trajectoryCodes = new Set(objectives.trajectories.flatMap((objective) => objective.subjectCodes));
  const electives = catalog.subjects.filter(
    (subject) => subject.type !== 'Obligatoria' && trajectoryCodes.has(subject.code),
  );
  const approved = electives
    .filter((subject) => stateForCode(subject.code, kardex).approved)
    .map((subject) => subject.code);
  const pending = electives
    .filter((subject) => !stateForCode(subject.code, kardex).approved)
    .map((subject) => subject.code);
  const required = objectives.licenciaturaElectiveRequirement;

  return {
    required,
    approved,
    pending,
    remaining: Math.max(0, required - approved.length),
    completed: approved.length >= required,
  };
}
