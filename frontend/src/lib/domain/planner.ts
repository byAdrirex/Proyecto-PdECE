import type {
  AcademicState,
  OfferAuxiliary,
  OfferGroup,
  ScheduleBlock,
} from './types';

export type PlannerMode = 'academic' | 'manual';
export type PlannerBlockType = 'CLASE' | 'AUX';

export type PlannerScheduleBlock = ScheduleBlock & {
  modality?: string | null;
};

export type PlannerAuxiliary = Omit<OfferAuxiliary, 'schedule'> & {
  schedule: PlannerScheduleBlock[];
};

export type PlannerGroup = Omit<OfferGroup, 'schedule' | 'auxiliaries'> & {
  schedule: PlannerScheduleBlock[];
  auxiliaries: PlannerAuxiliary[];
  modality?: string | null;
  _recomendado?: boolean | null;
  _calificacion_recomendacion?: number | null;
  _comentario_recomendacion?: string | null;
};

export interface PlannerWarning {
  code: string;
  group: string | null;
  message: string;
}

export interface PlannerConflict {
  subject1: string;
  group1: string | null;
  subject2: string;
  group2: string | null;
  day: string;
  start1: string;
  end1: string;
  type1: PlannerBlockType;
  start2: string;
  end2: string;
  type2: PlannerBlockType;
}

export interface PlannerPlan {
  mode: PlannerMode;
  year: number;
  term: number;
  includeAuxiliary: boolean;
  selectedSubjects: string[];
  selectedGroups: PlannerGroup[];
  conflicts: PlannerConflict[];
  warnings: PlannerWarning[];
}

export interface PlannerLimits {
  type: 'semestre regular' | 'intersemestral';
  normalMax: number;
  mesaMax: number;
  normalUsed: number;
  mesaUsed: number;
  normalAvailable: number;
  mesaAvailable: number;
}

export interface SelectionContext {
  academic?: AcademicState | null;
  prerequisites?: string[];
}

export interface SelectionResult {
  ok: boolean;
  plan: PlannerPlan;
  message: string | null;
}

export interface RemovalResult extends SelectionResult {}

export interface RecommendationConflict {
  day: string;
  start: string;
  end: string;
  subject: string;
  code: string;
  group: string | null;
  type: PlannerBlockType;
  selectedType: PlannerBlockType;
}

export interface GroupRecommendation {
  recommended: boolean | null;
  score: number;
  comment: string;
  label: 'RECOMENDADO' | 'ALTERNATIVA' | 'CONFLICTO';
  conflicts: RecommendationConflict[];
  conflictCount: number;
  _recomendado: boolean | null;
  _calificacion_recomendacion: number;
  _comentario_recomendacion: string;
}

export interface PlannerSummary {
  mode: PlannerMode;
  selectedSubjectCount: number;
  selectedGroupCount: number;
  limits: PlannerLimits;
  weeklyHours: number;
  conflicts: PlannerConflict[];
  conflictCount: number;
  warnings: PlannerWarning[];
  warningCount: number;
}

interface ComparableBlock {
  day: string;
  start: string;
  end: string;
  type: PlannerBlockType;
}

const DAY_ORDER = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA'] as const;
const DAY_NAMES: Record<string, string> = {
  LU: 'Lunes',
  MA: 'Martes',
  MI: 'Miercoles',
  JU: 'Jueves',
  VI: 'Viernes',
  SA: 'Sabado',
};

const recommendationMetadata = {
  _recomendado: null,
  _calificacion_recomendacion: null,
  _comentario_recomendacion: null,
} as const;

const groupNumber = (group: PlannerGroup): string => group.group ?? '?';

const isMesa = (group: PlannerGroup): boolean =>
  group.modality === 'E' || group.schedule.some((schedule) => schedule.modality === 'E');

const counts = (plan: PlannerPlan): { normal: number; mesa: number } =>
  plan.selectedGroups.reduce(
    (result, group) => {
      result[isMesa(group) ? 'mesa' : 'normal'] += 1;
      return result;
    },
    { normal: 0, mesa: 0 },
  );

const validBlock = (
  block: PlannerScheduleBlock,
  type: PlannerBlockType,
): ComparableBlock | null => {
  if (!block.day || !block.start || !block.end) return null;
  return { day: block.day, start: block.start, end: block.end, type };
};

const blocksFor = (group: PlannerGroup, includeAuxiliary: boolean): ComparableBlock[] => {
  const blocks = group.schedule.flatMap((block) => validBlock(block, 'CLASE') ?? []);
  if (!includeAuxiliary) return blocks;
  return blocks.concat(
    group.auxiliaries.flatMap((auxiliary) =>
      auxiliary.schedule.flatMap((block) => validBlock(block, 'AUX') ?? []),
    ),
  );
};

const overlaps = (left: ComparableBlock, right: ComparableBlock): boolean =>
  left.day === right.day && left.start < right.end && right.start < left.end;

const parseTime = (value: string): number | null => {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return null;
  return hour * 60 + minute;
};

const deadMinutes = (blocks: readonly ComparableBlock[]): number => {
  const byDay = new Map<string, Array<[number, number]>>();
  for (const block of blocks) {
    const start = parseTime(block.start);
    const end = parseTime(block.end);
    if (start == null || end == null) continue;
    const spans = byDay.get(block.day) ?? [];
    spans.push([start, end]);
    byDay.set(block.day, spans);
  }

  let total = 0;
  for (const spans of byDay.values()) {
    spans.sort((left, right) => left[0] - right[0]);
    for (let index = 0; index < spans.length - 1; index += 1) {
      const gap = spans[index + 1]![0] - spans[index]![1];
      if (gap > 0) total += gap;
    }
  }
  return total;
};

const dayRank = (day: string): number => {
  const rank = DAY_ORDER.indexOf(day as (typeof DAY_ORDER)[number]);
  return rank === -1 ? DAY_ORDER.length : rank;
};

export function createPlan(mode: PlannerMode, year: number, term: number): PlannerPlan {
  if (mode !== 'academic' && mode !== 'manual') {
    throw new Error("Modo invalido. Use 'academic' o 'manual'.");
  }
  if (![1, 2, 3, 4].includes(term)) {
    throw new Error('Gestion invalida. Use 1, 2, 3 o 4.');
  }
  return {
    mode,
    year,
    term,
    includeAuxiliary: true,
    selectedSubjects: [],
    selectedGroups: [],
    conflicts: [],
    warnings: [],
  };
}

export function limits(plan: PlannerPlan): PlannerLimits {
  const regular = plan.term === 1 || plan.term === 2;
  const normalMax = regular ? 8 : 2;
  const mesaMax = regular ? 2 : 0;
  const { normal, mesa } = counts(plan);
  return {
    type: regular ? 'semestre regular' : 'intersemestral',
    normalMax,
    mesaMax,
    normalUsed: normal,
    mesaUsed: mesa,
    normalAvailable: Math.max(0, normalMax - normal),
    mesaAvailable: Math.max(0, mesaMax - mesa),
  };
}

export function detectConflicts(
  plan: PlannerPlan,
  includeAuxiliary: boolean,
): PlannerConflict[] {
  const conflicts: PlannerConflict[] = [];
  for (let leftIndex = 0; leftIndex < plan.selectedGroups.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < plan.selectedGroups.length; rightIndex += 1) {
      const leftGroup = plan.selectedGroups[leftIndex]!;
      const rightGroup = plan.selectedGroups[rightIndex]!;
      if (leftGroup.code === rightGroup.code && leftGroup.group === rightGroup.group) continue;

      for (const left of blocksFor(leftGroup, includeAuxiliary)) {
        for (const right of blocksFor(rightGroup, includeAuxiliary)) {
          if (!overlaps(left, right)) continue;
          conflicts.push({
            subject1: leftGroup.code,
            group1: leftGroup.group,
            subject2: rightGroup.code,
            group2: rightGroup.group,
            day: left.day,
            start1: left.start,
            end1: left.end,
            type1: left.type,
            start2: right.start,
            end2: right.end,
            type2: right.type,
          });
        }
      }
    }
  }

  return conflicts.sort(
    (left, right) =>
      dayRank(left.day) - dayRank(right.day) ||
      left.start1.localeCompare(right.start1) ||
      left.subject1.localeCompare(right.subject1),
  );
}

export function selectGroup(
  plan: PlannerPlan,
  group: PlannerGroup,
  context: SelectionContext,
): SelectionResult {
  const number = groupNumber(group);
  if (
    plan.selectedGroups.some(
      (selected) => selected.code === group.code && selected.group === group.group,
    )
  ) {
    return {
      ok: false,
      plan,
      message: `El grupo ${number} de ${group.code} ya esta seleccionado.`,
    };
  }

  const academic = context.academic;
  if (plan.mode === 'academic' && academic?.status === 'BLOQUEADA') {
    return {
      ok: false,
      plan,
      message: `Materia bloqueada. Faltan prerrequisitos: ${academic.missingPrerequisites.join(', ')}`,
    };
  }
  if (plan.mode === 'academic' && academic?.status === 'APROBADA') {
    return {
      ok: false,
      plan,
      message: 'Esta materia ya esta aprobada en tu historial.',
    };
  }

  const currentLimits = limits(plan);
  const mesa = isMesa(group);
  if (mesa && currentLimits.mesaUsed >= currentLimits.mesaMax) {
    return {
      ok: false,
      plan,
      message: `Ya tienes ${currentLimits.mesaUsed} materias de mesa (maximo ${currentLimits.mesaMax}).`,
    };
  }
  if (
    !mesa &&
    currentLimits.normalUsed >= currentLimits.normalMax &&
    currentLimits.type === 'intersemestral'
  ) {
    return {
      ok: false,
      plan,
      message: `Ya tienes ${currentLimits.normalUsed} materias normales seleccionadas (maximo ${currentLimits.normalMax}).`,
    };
  }

  const warnings = [...plan.warnings];
  const structuralPrerequisites =
    context.prerequisites ?? academic?.missingPrerequisites ?? [];
  if (!mesa && currentLimits.normalUsed >= currentLimits.normalMax) {
    warnings.push({
      code: group.code,
      group: group.group,
      message:
        'Has superado las 8 materias recomendadas para un semestre regular. ' +
        'Puedes continuar, pero ten en cuenta la carga academica.',
    });
  }
  if (
    plan.mode === 'manual' &&
    structuralPrerequisites.length > 0
  ) {
    warnings.push({
      code: group.code,
      group: group.group,
      message:
        'Esta materia tiene prerrequisitos. En modo manual no se verificara tu historial ' +
        `academico. Prerrequisitos: ${structuralPrerequisites.join(', ')}`,
    });
  }

  const selectedGroup: PlannerGroup = { ...group, ...recommendationMetadata };
  const selectedGroups = [...plan.selectedGroups, selectedGroup];
  const nextPlan: PlannerPlan = {
    ...plan,
    selectedGroups,
    selectedSubjects: plan.selectedSubjects.includes(group.code)
      ? [...plan.selectedSubjects]
      : [...plan.selectedSubjects, group.code],
    warnings,
    conflicts: [],
  };
  nextPlan.conflicts = detectConflicts(nextPlan, nextPlan.includeAuxiliary);
  return { ok: true, plan: nextPlan, message: null };
}

export function removeGroup(
  plan: PlannerPlan,
  code: string,
  groupNumberToRemove: string,
): RemovalResult {
  const index = plan.selectedGroups.findIndex(
    (group) => group.code === String(code) && group.group === groupNumberToRemove,
  );
  if (index === -1) {
    return {
      ok: false,
      plan,
      message: `Grupo ${groupNumberToRemove} de ${code} no encontrado en el horario.`,
    };
  }

  const selectedGroups = plan.selectedGroups.filter((_, groupIndex) => groupIndex !== index);
  const hasAnotherGroup = selectedGroups.some((group) => group.code === String(code));
  const nextPlan: PlannerPlan = {
    ...plan,
    selectedGroups,
    selectedSubjects: hasAnotherGroup
      ? [...plan.selectedSubjects]
      : plan.selectedSubjects.filter((subject) => subject !== String(code)),
    warnings: plan.warnings.filter(
      (warning) =>
        !(warning.code === String(code) && warning.group === groupNumberToRemove),
    ),
    conflicts: [],
  };
  nextPlan.conflicts = detectConflicts(nextPlan, nextPlan.includeAuxiliary);
  return { ok: true, plan: nextPlan, message: null };
}

const conflictsWithSelection = (
  group: PlannerGroup,
  plan: PlannerPlan,
): RecommendationConflict[] => {
  const conflicts: RecommendationConflict[] = [];
  const candidateBlocks = blocksFor(group, plan.includeAuxiliary);
  for (const selected of plan.selectedGroups) {
    if (selected.code === group.code && selected.group === group.group) continue;
    for (const candidate of candidateBlocks) {
      for (const existing of blocksFor(selected, plan.includeAuxiliary)) {
        if (!overlaps(candidate, existing)) continue;
        conflicts.push({
          day: candidate.day,
          start: candidate.start,
          end: candidate.end,
          subject: selected.name ?? selected.code,
          code: selected.code,
          group: selected.group,
          type: candidate.type,
          selectedType: existing.type,
        });
      }
    }
  }
  return conflicts;
};

export function recommendGroup(
  group: PlannerGroup,
  plan: PlannerPlan,
  academic: AcademicState | null,
): GroupRecommendation {
  const conflicts = conflictsWithSelection(group, plan);
  const classConflicts = conflicts.filter(
    (conflict) => conflict.type === 'CLASE' && conflict.selectedType === 'CLASE',
  ).length;
  const auxiliaryConflicts = conflicts.length - classConflicts;
  let score = 90 - 25 * classConflicts - 12 * auxiliaryConflicts;

  const currentBlocks = plan.selectedGroups.flatMap((selected) =>
    blocksFor(selected, plan.includeAuxiliary),
  );
  const combinedBlocks = currentBlocks.concat(blocksFor(group, plan.includeAuxiliary));
  const deadMinuteDelta = deadMinutes(combinedBlocks) - deadMinutes(currentBlocks);
  if (deadMinuteDelta < 0) score += 5;
  else if (deadMinuteDelta > 0) score -= Math.min(10, Math.floor(deadMinuteDelta / 120));

  const days = new Set(combinedBlocks.map((block) => block.day));
  if (days.size > 4) score -= (days.size - 4) * 5;
  if (group.auxiliaries.length > 0) score += 3;
  score = Math.max(0, Math.min(100, Math.round(score)));

  const recommended = score >= 80 ? true : score >= 55 ? null : false;
  const label = score >= 80 ? 'RECOMENDADO' : score >= 55 ? 'ALTERNATIVA' : 'CONFLICTO';
  const commentParts: string[] = [];
  if (conflicts.length === 0) {
    commentParts.push('Sin conflictos con tu seleccion actual.');
    if (days.size <= 3) commentParts.push('Distribucion equilibrada de horarios.');
    if (deadMinuteDelta < 0) commentParts.push('Reduce horas muertas de tu horario.');
    if (group.auxiliaries.length > 0) commentParts.push('Dispone de auxiliar.');
  } else {
    for (const conflict of conflicts.slice(0, 3)) {
      commentParts.push(
        `Coincide con ${conflict.subject} (G${conflict.group ?? '?'}) el ` +
          `${DAY_NAMES[conflict.day] ?? conflict.day} ${conflict.start}-${conflict.end}.`,
      );
    }
    if (conflicts.length > 3) {
      commentParts.push(`Y ${conflicts.length - 3} choque(s) mas.`);
    }
    if (group.auxiliaries.length > 0) commentParts.push('Dispone de auxiliar.');
  }
  if (plan.mode === 'academic' && academic?.status === 'REPROBADA') {
    commentParts.push('Reprobada en tu historial: puedes volver a cursarla.');
  }
  if (plan.mode === 'academic' && academic?.status === 'EN_CURSO') {
    commentParts.push('Materia en curso en la gestion actual.');
  }
  const comment = commentParts.join(' ') || 'Seleccion posible.';

  return {
    recommended,
    score,
    comment,
    label,
    conflicts,
    conflictCount: conflicts.length,
    _recomendado: recommended,
    _calificacion_recomendacion: score,
    _comentario_recomendacion: comment,
  };
}

export function weeklyHours(plan: PlannerPlan): number {
  const minutes = plan.selectedGroups
    .flatMap((group) => blocksFor(group, plan.includeAuxiliary))
    .reduce((total, block) => {
      const start = parseTime(block.start);
      const end = parseTime(block.end);
      return start == null || end == null ? total : total + Math.max(0, end - start);
    }, 0);
  return minutes / 60;
}

export function planSummary(plan: PlannerPlan): PlannerSummary {
  const conflicts = detectConflicts(plan, plan.includeAuxiliary);
  return {
    mode: plan.mode,
    selectedSubjectCount: plan.selectedSubjects.length,
    selectedGroupCount: plan.selectedGroups.length,
    limits: limits(plan),
    weeklyHours: weeklyHours(plan),
    conflicts,
    conflictCount: conflicts.length,
    warnings: [...plan.warnings],
    warningCount: plan.warnings.length,
  };
}
