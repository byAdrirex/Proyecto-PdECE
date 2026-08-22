import { createElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import { normalizeAttempts } from '../lib/domain/kardex';
import { loadWorkspace, saveWorkspace } from '../lib/storage';
import { AcademicWorkspace } from './AcademicWorkspace';
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
    await click(buttonByName(rendered.container, 'Agregar ECONOMIA GENERAL como aprobada'));

    expect(rendered.container.textContent).toContain('ECONOMIA GENERAL');
    expect(loadWorkspace().kardex?.attempts['1304001']).toHaveLength(1);

    await click(buttonByName(rendered.container, 'Eliminar ECONOMIA GENERAL'));

    expect(loadWorkspace().kardex?.attempts['1304001']).toBeUndefined();
    expect(rendered.container.textContent).toContain('Todavia no registraste materias');
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
});
