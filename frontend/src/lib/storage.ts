import { normalizeAttempts } from './domain/kardex';
import type { KardexState } from './domain/types';
import type { PlannerMode, PlannerPlan } from './domain/planner';

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

const plannerPlan = (value: unknown): PlannerPlan | null =>
  isRecord(value) && plannerMode(value.mode) !== null
    ? value as unknown as PlannerPlan
    : null;

const normalizeWorkspace = (value: unknown): WorkspaceState => {
  if (!isRecord(value)) return emptyWorkspace();

  return {
    version: workspaceVersion,
    kardex: value.kardex == null ? null : normalizeAttempts(value.kardex),
    activeMentions: stringList(value.activeMentions),
    activeTechnicians: stringList(value.activeTechnicians),
    mode: plannerMode(value.mode),
    plan: plannerPlan(value.plan),
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
    return normalizeWorkspace(JSON.parse(stored));
  } catch {
    storage.removeItem(workspaceStorageKey);
    return emptyWorkspace();
  }
}

export function saveWorkspace(workspace: WorkspaceState): void {
  const storage = browserStorage();
  if (!storage) return;

  storage.setItem(workspaceStorageKey, JSON.stringify(normalizeWorkspace(workspace)));
}

export function clearWorkspace(): void {
  browserStorage()?.removeItem(workspaceStorageKey);
}
