import {
  detectConflicts,
  type PlannerBlockType,
  type PlannerConflict,
  type PlannerGroup,
  type PlannerPlan,
  type PlannerScheduleBlock,
} from './planner';

export interface CalendarTerm {
  startRecur: string;
  endRecur: string;
}

export interface CalendarEventProperties {
  type: PlannerBlockType;
  name: string;
  room: string;
  group: string | null;
  code: string;
  conflict: boolean;
  auxiliaryInstructor?: string;
}

export interface CalendarEvent {
  title: string;
  startRecur: string;
  endRecur: string;
  startTime: string;
  endTime: string;
  daysOfWeek: number[];
  backgroundColor: string;
  borderColor: string;
  textColor: string;
  extendedProps: CalendarEventProperties;
}

type ColorPair = readonly [background: string, border: string];

const DAY_NUMBERS: Record<string, number> = {
  LU: 1,
  MA: 2,
  MI: 3,
  JU: 4,
  VI: 5,
  SA: 6,
};

const PASTELS: readonly ColorPair[] = [
  ['#bfdbfe', '#1d4ed8'],
  ['#bbf7d0', '#16a34a'],
  ['#fde68a', '#b45309'],
  ['#fbcfe8', '#db2777'],
  ['#ddd6fe', '#7c3aed'],
  ['#a5f3fc', '#0e7490'],
  ['#fed7aa', '#ea580c'],
  ['#d1fae5', '#059669'],
  ['#e0e7ff', '#4f46e5'],
  ['#fce7f3', '#be185d'],
];

const CONFLICT_COLOR: ColorPair = ['#ef4444', '#b91c1c'];

const colorKey = (group: PlannerGroup): string => `${group.code}\u0000${group.group ?? ''}`;

const colorsForPlan = (plan: PlannerPlan): Map<string, ColorPair> => {
  const colors = new Map<string, ColorPair>();
  const nextIndex = new Map<string, number>();
  for (const group of plan.selectedGroups) {
    const key = colorKey(group);
    if (colors.has(key)) continue;
    const initial =
      nextIndex.get(group.code) ??
      [...group.code].reduce((total, character, index) =>
        total + character.charCodeAt(0) * (index + 1), 0) % PASTELS.length;
    colors.set(key, PASTELS[initial]!);
    nextIndex.set(group.code, (initial + 1) % PASTELS.length);
  }
  return colors;
};

const conflictKey = (
  code: string,
  group: string | null,
  type: PlannerBlockType,
  day: string,
  start: string,
  end: string,
): string => [code, group ?? '', type, day, start, end].join('\u0000');

const conflictBlocks = (conflicts: readonly PlannerConflict[]): Set<string> => {
  const blocks = new Set<string>();
  for (const conflict of conflicts) {
    blocks.add(conflictKey(
      conflict.subject1,
      conflict.group1,
      conflict.type1,
      conflict.day,
      conflict.start1,
      conflict.end1,
    ));
    blocks.add(conflictKey(
      conflict.subject2,
      conflict.group2,
      conflict.type2,
      conflict.day,
      conflict.start2,
      conflict.end2,
    ));
  }
  return blocks;
};

const eventForBlock = (
  group: PlannerGroup,
  block: PlannerScheduleBlock,
  type: PlannerBlockType,
  term: CalendarTerm,
  pastel: ColorPair,
  conflicts: ReadonlySet<string>,
  auxiliaryInstructor?: string | null,
): CalendarEvent | null => {
  if (!block.day || !block.start || !block.end) return null;
  const dayNumber = DAY_NUMBERS[block.day];
  if (dayNumber == null) return null;
  const isConflict = conflicts.has(
    conflictKey(group.code, group.group, type, block.day, block.start, block.end),
  );
  const [backgroundColor, borderColor] = isConflict ? CONFLICT_COLOR : pastel;
  const name = group.name ?? '?';
  const number = group.group ?? '?';
  return {
    title: `${type === 'AUX' ? 'AUX ' : ''}${name} (G${number})`,
    startRecur: term.startRecur,
    endRecur: term.endRecur,
    startTime: block.start,
    endTime: block.end,
    daysOfWeek: [dayNumber],
    backgroundColor,
    borderColor,
    textColor: isConflict ? '#ffffff' : '#1f2937',
    extendedProps: {
      type,
      name,
      room: block.room ?? '-',
      group: group.group,
      code: group.code,
      conflict: isConflict,
      ...(type === 'AUX'
        ? { auxiliaryInstructor: auxiliaryInstructor ?? '?' }
        : {}),
    },
  };
};

export function calendarEvents(plan: PlannerPlan, term: CalendarTerm): CalendarEvent[] {
  const conflicts = conflictBlocks(detectConflicts(plan, plan.includeAuxiliary));
  const colors = colorsForPlan(plan);
  const events: CalendarEvent[] = [];

  for (const group of plan.selectedGroups) {
    const pastel = colors.get(colorKey(group)) ?? PASTELS[0]!;
    for (const block of group.schedule) {
      const event = eventForBlock(group, block, 'CLASE', term, pastel, conflicts);
      if (event) events.push(event);
    }
    if (!plan.includeAuxiliary) continue;
    for (const auxiliary of group.auxiliaries) {
      for (const block of auxiliary.schedule) {
        const event = eventForBlock(
          group,
          block,
          'AUX',
          term,
          pastel,
          conflicts,
          auxiliary.name,
        );
        if (event) events.push(event);
      }
    }
  }
  return events;
}
