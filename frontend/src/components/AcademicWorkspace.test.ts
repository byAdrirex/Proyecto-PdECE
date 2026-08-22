import { createElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import { normalizeAttempts } from '../lib/domain/kardex';
import { loadWorkspace, saveWorkspace } from '../lib/storage';
import { AcademicWorkspace } from './AcademicWorkspace';
import { MallaExplorer } from './MallaExplorer';
import {
  buttonByName,
  click,
  enterValue,
  renderComponent,
  type RenderedComponent,
} from './test-utils';

let rendered: RenderedComponent | null = null;

afterEach(async () => {
  await rendered?.cleanup();
  rendered = null;
  localStorage.clear();
});

describe('AcademicWorkspace', () => {
  it('adds and removes a subject from a manual Kardex', async () => {
    rendered = await renderComponent(createElement(AcademicWorkspace, { view: 'progress' }));

    await click(buttonByName(rendered.container, 'Registro manual'));
    const search = rendered.container.querySelector<HTMLInputElement>('input[aria-label="Buscar materia"]');
    expect(search).not.toBeNull();
    await enterValue(search!, '1304001');
    const grade = rendered.container.querySelector<HTMLInputElement>(
      'input[aria-label="Nota final para ECONOMIA GENERAL"]',
    );
    expect(grade).not.toBeNull();
    await enterValue(grade!, '65');
    await click(buttonByName(rendered.container, 'Registrar ECONOMIA GENERAL'));

    expect(rendered.container.textContent).toContain('ECONOMIA GENERAL');
    expect(loadWorkspace().kardex?.attempts['1304001']).toHaveLength(1);

    await click(buttonByName(rendered.container, 'Eliminar ECONOMIA GENERAL'));

    expect(loadWorkspace().kardex?.attempts['1304001']).toBeUndefined();
    expect(rendered.container.textContent).toContain('Todavia no registraste materias');
  });

  it('derives failed and approved manual results from grades 0 through 100 in the active period', async () => {
    saveWorkspace({
      ...loadWorkspace(),
      kardex: normalizeAttempts({
        attempts: {},
        configuration: { currentYear: 2030, currentTerm: 1 },
      }),
    });
    rendered = await renderComponent(createElement(AcademicWorkspace, { view: 'progress' }));
    await click(buttonByName(rendered.container, 'Registro manual'));

    const search = rendered.container.querySelector<HTMLInputElement>('input[aria-label="Buscar materia"]')!;
    await enterValue(search, '1304001');
    await enterValue(
      rendered.container.querySelector<HTMLInputElement>('input[aria-label="Nota final para ECONOMIA GENERAL"]')!,
      '0',
    );
    await click(buttonByName(rendered.container, 'Registrar ECONOMIA GENERAL'));

    await enterValue(search, '1304004');
    await enterValue(
      rendered.container.querySelector<HTMLInputElement>('input[aria-label="Nota final para CALCULO"]')!,
      '51',
    );
    await click(buttonByName(rendered.container, 'Registrar CALCULO'));

    await enterValue(search, '1304003');
    await enterValue(
      rendered.container.querySelector<HTMLInputElement>('input[aria-label="Nota final para ALGEBRA"]')!,
      '100',
    );
    await click(buttonByName(rendered.container, 'Registrar ALGEBRA'));

    const saved = loadWorkspace().kardex!;
    expect(saved.attempts['1304001']?.[0]).toEqual(expect.objectContaining({
      final: 0, result: 'REP', year: 2030, term: 1,
    }));
    expect(saved.attempts['1304004']?.[0]).toEqual(expect.objectContaining({
      final: 51, result: 'APR', year: 2030, term: 1,
    }));
    expect(saved.attempts['1304003']?.[0]).toEqual(expect.objectContaining({
      final: 100, result: 'APR', year: 2030, term: 1,
    }));
    expect(rendered.container.textContent).toContain('Reprobada');
    expect(rendered.container.textContent).toContain('Aprobada');
  });

  it('shows progress derived from the persisted Kardex', async () => {
    saveWorkspace({
      ...loadWorkspace(),
      kardex: normalizeAttempts({
        subjects: [{ code: '1304001', attempts: [{ result: 'APR', final: 65 }] }],
      }),
    });

    rendered = await renderComponent(createElement(AcademicWorkspace, { view: 'progress' }));

    expect(rendered.container.textContent).toContain('Avance de materias obligatorias');
    expect(rendered.container.textContent).toContain('1 de 39');
    expect(rendered.container.textContent).toContain('2.6%');
    expect(rendered.container.textContent).toContain('ECONOMIA GENERAL');
  });

  it('shows mention and technician progress after their malla toggles persist', async () => {
    rendered = await renderComponent(createElement(MallaExplorer));
    await click(buttonByName(rendered.container, 'Activar ECONOMIA DEL DESARROLLO'));
    await click(buttonByName(rendered.container, 'Activar TECNICO SUPERIOR EN PROYECTOS DE INVERSION'));
    await rendered.cleanup();

    rendered = await renderComponent(createElement(AcademicWorkspace, { view: 'progress' }));

    expect(rendered.container.textContent).toContain('Progreso de trayectorias activas');
    expect(rendered.container.textContent).toContain('ECONOMIA DEL DESARROLLO');
    expect(rendered.container.textContent).toContain('0 de 9');
    expect(rendered.container.textContent).toContain('TECNICO SUPERIOR EN PROYECTOS DE INVERSION');
    expect(rendered.container.textContent).toContain('0 de 6');
  });
});
