import { describe, expect, it } from 'vitest';

import { calendarEvents, type CalendarTerm } from './calendar';
import {
  createPlan,
  selectGroup,
  type PlannerGroup,
  type PlannerScheduleBlock,
} from './planner';

const semester2026Two: CalendarTerm = {
  startRecur: '2026-08-17',
  endRecur: '2026-12-19',
};

const schedule = (
  day: string,
  start = '08:15',
  end = '09:45',
): PlannerScheduleBlock => ({ day, start, end, room: 'E530' });

const group = (
  code: string,
  groupNumber: string,
  blocks: PlannerScheduleBlock[],
): PlannerGroup => ({
  code,
  name: `MATERIA ${code}`,
  level: 'A',
  group: groupNumber,
  instructor: 'DOCENTE TEST',
  schedule: blocks,
  auxiliaries: [],
});

describe('calendarEvents', () => {
  it('maps Monday through Saturday and emits semester recurrence metadata', () => {
    const days = ['LU', 'MA', 'MI', 'JU', 'VI', 'SA'];
    const selected = days.reduce(
      (plan, day, index) =>
        selectGroup(plan, group(`D${index + 1}`, '01', [schedule(day)]), {}).plan,
      createPlan('manual', 2026, 2),
    );

    const events = calendarEvents(selected, semester2026Two);

    expect(events.map((event) => event.daysOfWeek)).toEqual([[1], [2], [3], [4], [5], [6]]);
    expect(events[0]).toEqual(expect.objectContaining({
      startRecur: '2026-08-17',
      endRecur: '2026-12-19',
      startTime: '08:15',
      endTime: '09:45',
    }));
  });

  it('distinguishes class and auxiliary events while sharing the group pastel', () => {
    const withAuxiliary: PlannerGroup = {
      ...group('1304001', '01', [schedule('MA', '09:45', '11:15')]),
      name: 'ECONOMIA GENERAL',
      auxiliaries: [{
        name: 'AUX NAME',
        schedule: [schedule('LU', '11:15', '12:45')],
      }],
    };
    const plan = selectGroup(createPlan('manual', 2026, 2), withAuxiliary, {}).plan;

    const [classEvent, auxiliaryEvent] = calendarEvents(plan, semester2026Two);

    expect(classEvent).toEqual(expect.objectContaining({
      title: 'ECONOMIA GENERAL (G01)',
      daysOfWeek: [2],
      textColor: '#1f2937',
      extendedProps: expect.objectContaining({ type: 'CLASE', room: 'E530' }),
    }));
    expect(auxiliaryEvent).toEqual(expect.objectContaining({
      title: 'AUX ECONOMIA GENERAL (G01)',
      daysOfWeek: [1],
      extendedProps: expect.objectContaining({ type: 'AUX', auxiliaryInstructor: 'AUX NAME' }),
    }));
    expect(auxiliaryEvent?.backgroundColor).toBe(classEvent?.backgroundColor);
    expect(auxiliaryEvent?.borderColor).toBe(classEvent?.borderColor);
    expect(classEvent?.backgroundColor).toMatch(/^#[a-f0-9]{6}$/);
    expect(classEvent?.backgroundColor).not.toBe('#ef4444');
  });

  it('rotates pastel colors for different groups of the same subject', () => {
    let plan = createPlan('manual', 2026, 2);
    plan = selectGroup(plan, group('COLOR01', '01', [schedule('LU')]), {}).plan;
    plan = selectGroup(plan, group('COLOR01', '02', [schedule('MA')]), {}).plan;

    const events = calendarEvents(plan, semester2026Two);

    expect(events).toHaveLength(2);
    expect(events[0]?.backgroundColor).not.toBe(events[1]?.backgroundColor);
  });

  it('colors only overlapping blocks red and marks them as conflicts', () => {
    let plan = createPlan('manual', 2026, 2);
    plan = selectGroup(
      plan,
      group('RED1', '01', [schedule('MA', '09:45', '11:15'), schedule('JU', '08:00', '09:30')]),
      {},
    ).plan;
    plan = selectGroup(
      plan,
      group('RED2', '01', [schedule('MA', '10:00', '11:30')]),
      {},
    ).plan;

    const events = calendarEvents(plan, semester2026Two);
    const red = events.filter((event) => event.backgroundColor === '#ef4444');
    const safe = events.filter((event) => event.backgroundColor !== '#ef4444');

    expect(red).toHaveLength(2);
    expect(red.every((event) => event.borderColor === '#b91c1c')).toBe(true);
    expect(red.every((event) => event.extendedProps.conflict)).toBe(true);
    expect(safe).toHaveLength(1);
    expect(safe[0]?.extendedProps.conflict).toBe(false);
  });

  it('omits auxiliary events when the plan disables them', () => {
    const selected = selectGroup(
      createPlan('manual', 2026, 2),
      {
        ...group('NOAUX', '01', [schedule('LU')]),
        auxiliaries: [{ name: 'AUX', schedule: [schedule('MA')] }],
      },
      {},
    ).plan;

    const events = calendarEvents({ ...selected, includeAuxiliary: false }, semester2026Two);

    expect(events).toHaveLength(1);
    expect(events[0]?.extendedProps.type).toBe('CLASE');
  });
});
