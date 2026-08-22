import { normalizeAttempts } from './domain/kardex';
import type { KardexState } from './domain/types';
import type {
  PlannerAuxiliary,
  PlannerConflict,
  PlannerGroup,
  PlannerMode,
  PlannerPlan,
  PlannerScheduleBlock,
  PlannerWarning,
} from './domain/planner';

const workspaceVersion = 1 as const;

export const workspaceStorageKey = 'pde.workspace.v1';

export interface WorkspaceState {
  version: typeof workspaceVersion;
  kardex: KardexState | null;
  activeMentions: string[];
  activeTechnicians: string[];
  mode: PlannerMode | null;
  plan: PlannerPlan | null;
}

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const emptyWorkspace = (): WorkspaceState => ({
  version: workspaceVersion,
  kardex: null,
  activeMentions: [],
  activeTechnicians: [],
  mode: null,
  plan: null,
});

const stringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean),
  )];
};

const plannerMode = (value: unknown): PlannerMode | null =>
  value === 'academic' || value === 'manual' ? value : null;

const nullableString = (value: unknown): value is string | null =>
  value === null || typeof value === 'string';

const optionalNullableString = (value: unknown): value is string | null | undefined =>
  value === undefined || nullableString(value);

const isScheduleBlock = (value: unknown): value is PlannerScheduleBlock =>
  isRecord(value)
  && nullableString(value.day)
  && nullableString(value.start)
  && nullableString(value.end)
  && nullableString(value.room)
  && optionalNullableString(value.modality);

const isAuxiliary = (value: unknown): value is PlannerAuxiliary =>
  isRecord(value)
  && nullableString(value.name)
  && Array.isArray(value.schedule)
  && value.schedule.every(isScheduleBlock);

const optionalRecommendationFields = (value: UnknownRecord): boolean =>
  (value._recomendado === undefined
    || value._recomendado === null
    || typeof value._recomendado === 'boolean')
  && (value._calificacion_recomendacion === undefined
    || value._calificacion_recomendacion === null
    || typeof value._calificacion_recomendacion === 'number')
  && optionalNullableString(value._comentario_recomendacion);

const isPlannerGroup = (value: unknown): value is PlannerGroup =>
  isRecord(value)
  && typeof value.code === 'string'
  && nullableString(value.name)
  && nullableString(value.level)
  && nullableString(value.group)
  && nullableString(value.instructor)
  && Array.isArray(value.schedule)
  && value.schedule.every(isScheduleBlock)
  && Array.isArray(value.auxiliaries)
  && value.auxiliaries.every(isAuxiliary)
  && optionalNullableString(value.modality)
  && optionalRecommendationFields(value);

const blockType = (value: unknown): boolean => value === 'CLASE' || value === 'AUX';

const isPlannerConflict = (value: unknown): value is PlannerConflict =>
  isRecord(value)
  && typeof value.subject1 === 'string'
  && nullableString(value.group1)
  && typeof value.subject2 === 'string'
  && nullableString(value.group2)
  && typeof value.day === 'string'
  && typeof value.start1 === 'string'
  && typeof value.end1 === 'string'
  && blockType(value.type1)
  && typeof value.start2 === 'string'
  && typeof value.end2 === 'string'
  && blockType(value.type2);

const isPlannerWarning = (value: unknown): value is PlannerWarning =>
  isRecord(value)
  && typeof value.code === 'string'
  && nullableString(value.group)
  && typeof value.message === 'string';

const isPlannerPlan = (value: unknown): value is PlannerPlan =>
  isRecord(value)
  && plannerMode(value.mode) !== null
  && typeof value.year === 'number'
  && Number.isInteger(value.year)
  && typeof value.term === 'number'
  && Number.isInteger(value.term)
  && typeof value.includeAuxiliary === 'boolean'
  && Array.isArray(value.selectedSubjects)
  && value.selectedSubjects.every((code) => typeof code === 'string')
  && Array.isArray(value.selectedGroups)
  && value.selectedGroups.every(isPlannerGroup)
  && Array.isArray(value.conflicts)
  && value.conflicts.every(isPlannerConflict)
  && Array.isArray(value.warnings)
  && value.warnings.every(isPlannerWarning);

const nullableNumber = (value: unknown): boolean =>
  value === null || (typeof value === 'number' && Number.isFinite(value));

const isKardexState = (value: unknown): boolean =>
  isRecord(value)
  && isRecord(value.attempts)
  && Object.values(value.attempts).every(
    (attempts) => Array.isArray(attempts) && attempts.every(isRecord),
  )
  && nullableNumber(value.currentYear)
  && nullableNumber(value.currentTerm);

const normalizeWorkspace = (value: unknown): WorkspaceState | null => {
  if (!isRecord(value)
    || value.version !== workspaceVersion
    || (value.kardex !== null && !isKardexState(value.kardex))
    || !Array.isArray(value.activeMentions)
    || !value.activeMentions.every((item) => typeof item === 'string')
    || !Array.isArray(value.activeTechnicians)
    || !value.activeTechnicians.every((item) => typeof item === 'string')
    || (value.mode !== null && plannerMode(value.mode) === null)
    || (value.plan !== null && !isPlannerPlan(value.plan))) {
    return null;
  }

  return {
    version: workspaceVersion,
    kardex: value.kardex == null ? null : normalizeAttempts(value.kardex),
    activeMentions: stringList(value.activeMentions),
    activeTechnicians: stringList(value.activeTechnicians),
    mode: plannerMode(value.mode),
    plan: value.plan,
  };
};

const browserStorage = (): Storage | null => {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
};

export function loadWorkspace(): WorkspaceState {
  const storage = browserStorage();
  if (!storage) return emptyWorkspace();

  const stored = storage.getItem(workspaceStorageKey);
  if (stored === null) return emptyWorkspace();

  try {
    const workspace = normalizeWorkspace(JSON.parse(stored));
    if (workspace) return workspace;
    storage.removeItem(workspaceStorageKey);
    return emptyWorkspace();
  } catch {
    storage.removeItem(workspaceStorageKey);
    return emptyWorkspace();
  }
}

export function saveWorkspace(workspace: WorkspaceState): void {
  const storage = browserStorage();
  if (!storage) return;

  const normalized = normalizeWorkspace(workspace);
  if (!normalized) throw new TypeError('El estado del espacio de trabajo no es valido.');
  storage.setItem(workspaceStorageKey, JSON.stringify(normalized));
}

export function clearWorkspace(): void {
  browserStorage()?.removeItem(workspaceStorageKey);
}
