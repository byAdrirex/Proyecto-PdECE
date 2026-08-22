import { createElement } from 'react';
import { afterEach, describe, expect, it } from 'vitest';

import offerFixture from '../data/offer.json';
import { createPlan, selectGroup } from '../lib/domain/planner';
import type { Offer } from '../lib/domain/types';
import { CalendarView } from './CalendarView';
import { renderComponent, type RenderedComponent } from './test-utils';

const offer = offerFixture as Offer;
let rendered: RenderedComponent | null = null;

afterEach(async () => {
  await rendered?.cleanup();
  rendered = null;
});

describe('CalendarView', () => {
  it('renders Spanish event labels from the real calendar domain output', async () => {
    const group = offer.groupsBySubject['1304001']?.[0];
    expect(group).toBeDefined();
    const plan = selectGroup(createPlan('manual', offer.year, offer.term), group!, {}).plan;

    rendered = await renderComponent(createElement(CalendarView, { plan }));

    expect(rendered.container.textContent).toContain('Mi horario semanal');
    expect(rendered.container.textContent).toContain('ECONOMIA GENERAL (G01)');
    expect(rendered.container.textContent).toContain('Martes 09:45–11:15');
    expect(rendered.container.textContent).toContain('Aula:');
    const calendar = rendered.container.querySelector('[data-slot-min-time]');
    expect(calendar?.getAttribute('data-slot-min-time')).toBe('06:45:00');
    expect(calendar?.getAttribute('data-slot-max-time')).toBe('21:45:00');
  });
});
