import { describe, expect, it } from 'vitest';

import offerFixture from '../../data/offer.json';
import {
  createPlan,
  detectConflicts,
  limits,
  planSummary,
  recommendGroup,
  removeGroup,
  selectGroup,
  weeklyHours,
  type PlannerGroup,
  type SelectionContext,
} from './planner';
import type { AcademicState, Offer } from './types';

const offer = offerFixture as Offer;

const block = (
  day: string,
  start: string,
  end: string,
  modality?: string,
) => ({ day, start, end, room: 'E530', modality });

const group = (
  code: string,
  groupNumber: string,
  day = 'LU',
  start = '08:15',
  end = '09:45',
  modality?: string,
): PlannerGroup => ({
  code,
  name: `MATERIA ${code}`,
  level: 'A',
  group: groupNumber,
  instructor: 'DOCENTE TEST',
  schedule: [block(day, start, end, modality)],
  auxiliaries: [],
});

const contextFor = (
  status: AcademicState['status'],
  missingPrerequisites: string[] = [],
): SelectionContext => ({
  academic: {
    code: 'TEST',
    status,
    kardexStatus: status === 'APROBADA' ? 'APROBADA' : 'SIN_HISTORIAL',
    provisional: false,
    missingPrerequisites,
    offered: true,
    offerStatus: 'OFERTADA',
    groups: [],
  },
});

describe('planner limits and selection', () => {
  it('uses regular limits and keeps the ninth normal subject selectable with a warning', () => {
    let plan = createPlan('manual', 2026, 2);

    expect(limits(plan)).toEqual({
      type: 'semestre regular',
      normalMax: 8,
      mesaMax: 2,
      normalUsed: 0,
      mesaUsed: 0,
      normalAvailable: 8,
      mesaAvailable: 2,
    });

    for (let index = 0; index < 9; index += 1) {
      const selected = selectGroup(
        plan,
        group(`N${index}`, '01', 'LU', `${String(index + 7).padStart(2, '0')}:00`, `${String(index + 8).padStart(2, '0')}:00`),
        {},
      );
      expect(selected.ok).toBe(true);
      plan = selected.plan;
    }

    expect(limits(plan).normalUsed).toBe(9);
    expect(plan.warnings.at(-1)?.message).toContain('8 materias');
  });

  it('caps regular mesa groups at two', () => {
    let plan = createPlan('manual', 2026, 2);
    for (const code of ['M1', 'M2']) {
      const result = selectGroup(plan, group(code, '01', 'LU', '08:00', '09:00', 'E'), {});
      expect(result.ok).toBe(true);
      plan = result.plan;
    }

    const rejected = selectGroup(plan, group('M3', '01', 'MA', '08:00', '09:00', 'E'), {});

    expect(rejected.ok).toBe(false);
    expect(rejected.message).toContain('mesa');
    expect(rejected.plan).toBe(plan);
  });

  it('uses a two-subject intersemester limit and disallows mesa groups', () => {
    let plan = createPlan('manual', 2026, 3);
    expect(limits(plan)).toEqual(expect.objectContaining({
      type: 'intersemestral', normalMax: 2, mesaMax: 0,
    }));

    for (const code of ['I1', 'I2']) {
      const result = selectGroup(plan, group(code, '01'), {});
      expect(result.ok).toBe(true);
      plan = result.plan;
    }

    expect(selectGroup(plan, group('I3', '01'), {}).ok).toBe(false);
    expect(selectGroup(createPlan('manual', 2026, 3), group('ME', '01', 'LU', '08:00', '09:00', 'E'), {}).ok).toBe(false);
  });

  it('rejects selecting the same subject group twice without mutating the plan', () => {
    const initial = createPlan('manual', 2026, 2);
    const first = selectGroup(initial, group('1304001', '01'), {});
    const duplicate = selectGroup(first.plan, group('1304001', '01'), {});

    expect(initial.selectedGroups).toEqual([]);
    expect(duplicate.ok).toBe(false);
    expect(duplicate.message).toBe('El grupo 01 de 1304001 ya esta seleccionado.');
    expect(duplicate.plan.selectedGroups).toHaveLength(1);
    expect(duplicate.plan.selectedGroups[0]).toEqual(expect.objectContaining({
      _recomendado: null,
      _calificacion_recomendacion: null,
      _comentario_recomendacion: null,
    }));
  });

  it('rejects blocked and approved subjects in academic mode', () => {
    const plan = createPlan('academic', 2026, 2);

    const blocked = selectGroup(
      plan,
      group('1304007', '01'),
      contextFor('BLOQUEADA', ['1304001', '1304004']),
    );
    const approved = selectGroup(
      plan,
      group('1304001', '01'),
      contextFor('APROBADA'),
    );

    expect(blocked.ok).toBe(false);
    expect(blocked.message).toContain('1304001, 1304004');
    expect(approved.ok).toBe(false);
    expect(approved.message).toContain('aprobada');
  });

  it('allows manual selection and records prerequisite warnings', () => {
    const result = selectGroup(
      createPlan('manual', 2026, 2),
      group('1304007', '01'),
      contextFor('BLOQUEADA', ['1304001', '1304004']),
    );

    expect(result.ok).toBe(true);
    expect(result.plan.warnings).toEqual([
      expect.objectContaining({
        code: '1304007',
        group: '01',
        message: expect.stringContaining('modo manual'),
      }),
    ]);
  });

  it('warns in manual mode from structural prerequisites even when none are missing', () => {
    const result = selectGroup(
      createPlan('manual', 2026, 2),
      group('1304026', '01'),
      {
        ...contextFor('REPROBADA'),
        prerequisites: ['1304007', '1304016'],
      },
    );

    expect(result.ok).toBe(true);
    expect(result.plan.warnings).toEqual([
      expect.objectContaining({
        code: '1304026',
        message: expect.stringContaining('1304007, 1304016'),
      }),
    ]);
  });
});

describe('planner conflicts, recommendations and summary', () => {
  it('detects overlapping classes, treats adjacent blocks as compatible and orders LU-SA', () => {
    const saturdayA = group('SA1', '01', 'SA', '08:00', '09:30');
    const saturdayB = group('SA2', '01', 'SA', '09:00', '10:30');
    const mondayA = group('LU1', '01', 'LU', '08:00', '09:30');
    const mondayB = group('LU2', '01', 'LU', '09:00', '10:30');
    const adjacent = group('OK', '01', 'LU', '10:30', '12:00');
    const plan = {
      ...createPlan('manual', 2026, 2),
      selectedGroups: [saturdayA, saturdayB, mondayA, mondayB, adjacent],
      selectedSubjects: ['SA1', 'SA2', 'LU1', 'LU2', 'OK'],
    };

    const conflicts = detectConflicts(plan, true);

    expect(conflicts.map((conflict) => conflict.day)).toEqual(['LU', 'SA']);
    expect(conflicts[0]).toEqual(expect.objectContaining({
      subject1: 'LU1', subject2: 'LU2', type1: 'CLASE', type2: 'CLASE',
    }));
  });

  it('includes auxiliary overlaps only when requested', () => {
    const withAuxiliary: PlannerGroup = {
      ...group('AUX1', '01', 'MA', '08:00', '09:30'),
      auxiliaries: [{ name: 'AUX TEST', schedule: [block('LU', '10:00', '11:30')] }],
    };
    const regular = group('CLS1', '01', 'LU', '10:30', '12:00');
    const plan = {
      ...createPlan('manual', 2026, 2),
      selectedGroups: [withAuxiliary, regular],
      selectedSubjects: ['AUX1', 'CLS1'],
    };

    expect(detectConflicts(plan, false)).toEqual([]);
    expect(detectConflicts(plan, true)).toEqual([
      expect.objectContaining({ type1: 'AUX', type2: 'CLASE' }),
    ]);
  });

  it('scores compatible and conflicting recommendations with the Python weights', () => {
    const emptyPlan = createPlan('manual', 2026, 2);
    const compatible = recommendGroup(group('C1', '01'), emptyPlan, null);
    const selected = selectGroup(emptyPlan, group('C1', '01'), {}).plan;
    const conflicting = recommendGroup(group('C2', '01', 'LU', '09:00', '10:30'), selected, null);

    expect(compatible).toEqual(expect.objectContaining({
      recommended: true,
      score: 90,
      label: 'RECOMENDADO',
      conflictCount: 0,
    }));
    expect(conflicting).toEqual(expect.objectContaining({
      recommended: null,
      score: 65,
      label: 'ALTERNATIVA',
      conflictCount: 1,
    }));
    expect(conflicting.comment).toContain('Coincide con MATERIA C1 (G01)');
  });

  it.each([
    ['REPROBADA', 'Reprobada en tu historial'],
    ['EN_CURSO', 'Materia en curso'],
  ] as const)(
    'adds %s history commentary only in academic mode',
    (status, commentary) => {
      const academic = contextFor(status).academic!;

      const manual = recommendGroup(
        group('H1', '01'),
        createPlan('manual', 2026, 2),
        academic,
      );
      const academicMode = recommendGroup(
        group('H1', '01'),
        createPlan('academic', 2026, 2),
        academic,
      );

      expect(manual.comment).not.toContain(commentary);
      expect(academicMode.comment).toContain(commentary);
    },
  );

  it('removes a group, its warning and stale conflicts', () => {
    let plan = selectGroup(
      createPlan('manual', 2026, 2),
      group('R1', '01'),
      contextFor('BLOQUEADA', ['P1']),
    ).plan;
    plan = selectGroup(plan, group('R2', '01', 'LU', '09:00', '10:30'), {}).plan;
    expect(plan.conflicts).toHaveLength(1);
    expect(planSummary(plan)).toEqual(expect.objectContaining({
      conflictCount: 1,
      conflicts: [expect.objectContaining({ subject1: 'R1', subject2: 'R2' })],
      warningCount: 1,
    }));

    const removed = removeGroup(plan, 'R1', '01');

    expect(removed.ok).toBe(true);
    expect(removed.plan.selectedSubjects).toEqual(['R2']);
    expect(removed.plan.warnings).toEqual([]);
    expect(removed.plan.conflicts).toEqual([]);
    expect(plan.selectedGroups).toHaveLength(2);
  });

  it('consumes normalized offer groups and reports hours, conflicts and warnings in the summary', () => {
    const fixtureGroup = offer.groupsBySubject['1304001']?.[0];
    expect(fixtureGroup).toBeDefined();
    const selected = selectGroup(createPlan('manual', offer.year, offer.term), fixtureGroup!, {}).plan;

    expect(weeklyHours(selected)).toBe(4.5);
    expect(planSummary(selected)).toEqual(expect.objectContaining({
      selectedSubjectCount: 1,
      selectedGroupCount: 1,
      weeklyHours: 4.5,
      conflictCount: 0,
      warningCount: 0,
    }));
  });
});
