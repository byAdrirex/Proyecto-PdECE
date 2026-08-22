import { createElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import { loadWorkspace } from '../lib/storage';
import { HorarioApp } from './HorarioApp';
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

const searchAndSelect = async (
  container: HTMLElement,
  query: string,
  subject: string,
  group: string,
): Promise<void> => {
  const search = container.querySelector<HTMLInputElement>('input[aria-label="Buscar materia para horario"]');
  expect(search).not.toBeNull();
  await enterValue(search!, query);
  await click(buttonByName(container, `Ver grupos de ${subject}`));
  await click(buttonByName(container, `Agregar grupo ${group} de ${subject}`));
};

describe('HorarioApp', () => {
  it('selects and removes a real offer group while persisting the plan', async () => {
    rendered = await renderComponent(createElement(HorarioApp));
    await click(buttonByName(rendered.container, 'Planificar sin Kardex'));

    await searchAndSelect(rendered.container, '1304001', 'ECONOMIA GENERAL', '01');

    expect(rendered.container.textContent).toContain('1 materia seleccionada');
    expect(rendered.container.textContent).toContain('4.5 horas semanales');
    expect(loadWorkspace().plan?.selectedGroups[0]?.code).toBe('1304001');

    await click(buttonByName(rendered.container, 'Quitar ECONOMIA GENERAL grupo 01'));

    expect(rendered.container.textContent).toContain('0 materias seleccionadas');
    expect(loadWorkspace().plan?.selectedGroups).toEqual([]);
  });

  it('reports a conflict after selecting overlapping real groups', async () => {
    rendered = await renderComponent(createElement(HorarioApp));
    await click(buttonByName(rendered.container, 'Planificar sin Kardex'));

    await searchAndSelect(rendered.container, '1304001', 'ECONOMIA GENERAL', '01');
    await searchAndSelect(
      rendered.container,
      '1304002',
      'TALLER DE LENGUAJE Y REDACCION',
      '02',
    );

    expect(rendered.container.textContent).toContain('1 conflicto de horario');
    expect(rendered.container.textContent).toContain('Martes 09:45–11:15');
    expect(loadWorkspace().plan?.conflicts).toHaveLength(1);
  });
});
