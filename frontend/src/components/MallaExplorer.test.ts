import { afterEach, describe, expect, it } from 'vitest';
import { createElement } from 'react';

import { MallaExplorer } from './MallaExplorer';
import { act } from 'react';
import { buttonByName, click, elementByText, renderComponent, type RenderedComponent } from './test-utils';

let rendered: RenderedComponent | null = null;

afterEach(async () => {
  await rendered?.cleanup();
  rendered = null;
  localStorage.clear();
});

describe('MallaExplorer', () => {
  it('opens a subject dialog with prerequisite and dependent information', async () => {
    rendered = await renderComponent(createElement(MallaExplorer));

    await click(elementByText(rendered.container, 'ECONOMIA GENERAL'));

    const dialog = rendered.container.querySelector('[role="dialog"]');
    expect(dialog?.getAttribute('aria-label')).toBe('Detalle de ECONOMIA GENERAL');
    expect(dialog?.textContent).toContain('1304001');
    expect(dialog?.textContent).toContain('No requiere prerrequisitos');
    expect(dialog?.textContent).toContain('Materias que habilita');
    expect(dialog?.textContent).toContain('MICROECONOMIA I');
    const connections = rendered.container.querySelector('[aria-label="Conexiones de ECONOMIA GENERAL"]');
    expect(connections?.textContent).toContain('ECONOMIA GENERAL → MICROECONOMIA I');
    expect(document.activeElement?.getAttribute('aria-label')).toBe('Cerrar detalle');

    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })));
    expect(rendered.container.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement?.textContent).toContain('ECONOMIA GENERAL');
  });

  it('renders all nine semesters and persists active trajectory selections', async () => {
    rendered = await renderComponent(createElement(MallaExplorer));

    expect(rendered.container.querySelectorAll('[data-semester]')).toHaveLength(9);
    await click(buttonByName(rendered.container, 'Activar ECONOMIA DEL DESARROLLO'));

    expect(localStorage.getItem('pde.workspace.v1')).toContain('M01');
    expect(rendered.container.querySelector('[aria-pressed="true"]')?.textContent).toContain(
      'ECONOMIA DEL DESARROLLO',
    );
  });
});
