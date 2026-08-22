import { afterEach, describe, expect, it } from 'vitest';
import { createElement } from 'react';

import { MallaExplorer } from './MallaExplorer';
import { click, elementByText, renderComponent, type RenderedComponent } from './test-utils';

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
  });

  it('renders all nine semesters and persists active trajectory selections', async () => {
    rendered = await renderComponent(createElement(MallaExplorer));

    expect(rendered.container.querySelectorAll('[data-semester]')).toHaveLength(9);
    await click(elementByText(rendered.container, 'ECONOMIA DEL DESARROLLO'));

    expect(localStorage.getItem('pde.workspace.v1')).toContain('M01');
    expect(rendered.container.querySelector('[aria-pressed="true"]')?.textContent).toContain(
      'ECONOMIA DEL DESARROLLO',
    );
  });
});
