import { Calendar, type CalendarOptions } from '@fullcalendar/core';
import esLocale from '@fullcalendar/core/locales/es';
import timeGridPlugin from '@fullcalendar/timegrid';
import { useEffect, useMemo, useRef } from 'react';

import { calendarEvents, type CalendarEvent } from '../lib/domain/calendar';
import type { PlannerPlan } from '../lib/domain/planner';

const semester2026Two = { startRecur: '2026-08-17', endRecur: '2026-12-19' };
const dayNames: Record<number, string> = {
  1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes', 6: 'Sábado',
};

export interface CalendarViewProps {
  plan: PlannerPlan;
}

const timeRange = (event: CalendarEvent): string =>
  `${dayNames[event.daysOfWeek[0] ?? 0] ?? ''} ${event.startTime}–${event.endTime}`;

export function CalendarView({ plan }: CalendarViewProps) {
  const calendarElement = useRef<HTMLDivElement>(null);
  const events = useMemo(() => calendarEvents(plan, semester2026Two), [plan]);

  useEffect(() => {
    if (!calendarElement.current) return;
    let calendar: Calendar | null = null;
    try {
      const options = {
        plugins: [timeGridPlugin],
        initialView: 'timeGridWeek',
        locale: esLocale,
        headerToolbar: false,
        firstDay: 1,
        hiddenDays: [0],
        allDaySlot: false,
        slotDuration: '01:30:00',
        slotMinTime: '06:45:00',
        slotMaxTime: '21:45:00',
        slotLabelInterval: '01:30:00',
        height: 'auto',
        expandRows: false,
        nowIndicator: false,
        dayHeaderFormat: { weekday: 'long' },
        eventDisplay: 'block',
        displayEventTime: false,
        events,
        slotLabelContent: ({ date }) => {
          const end = new Date(date.getTime() + 90 * 60 * 1000);
          const format = (value: Date) => `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`;
          return { html: `<span class="calendar-time-range">${format(date)} – ${format(end)}</span>` };
        },
        eventContent: ({ event }) => {
          const props = event.extendedProps as CalendarEvent['extendedProps'];
          const wrapper = document.createElement('div');
          wrapper.className = `calendar-event${props.conflict ? ' calendar-event--conflict' : ''}`;
          const title = document.createElement('strong');
          title.textContent = props.name;
          const details = document.createElement('span');
          details.textContent = `Aula: ${props.room} · Grupo: ${props.group ?? '-'}`;
          wrapper.append(title, details);
          if (props.type === 'AUX') {
            const auxiliary = document.createElement('small');
            auxiliary.textContent = `[AUX] ${props.auxiliaryInstructor ?? ''}`;
            wrapper.append(auxiliary);
          }
          if (props.conflict) {
            const warning = document.createElement('small');
            warning.textContent = 'Conflicto de horario';
            wrapper.append(warning);
          }
          return { domNodes: [wrapper] };
        },
      } as CalendarOptions;
      calendar = new Calendar(calendarElement.current, options);
      calendar.render();
      const axis = calendarElement.current.querySelector('.fc-timegrid-axis-cushion');
      if (axis) axis.textContent = 'Hora';
    } catch {
      calendarElement.current.dataset.fallback = 'true';
    }
    return () => calendar?.destroy();
  }, [events]);

  return (
    <section
      className="calendar-card surface"
      data-slot-min-time="06:45:00"
      data-slot-max-time="21:45:00"
      aria-labelledby="weekly-calendar-title"
    >
      <div className="section-heading">
        <div><p className="eyebrow">Lunes a sábado</p><h2 id="weekly-calendar-title">Mi horario semanal</h2></div>
        <span>{events.length} bloques</span>
      </div>
      {events.length === 0 && <p className="empty-state">Selecciona materias para ir llenando tu horario.</p>}
      <div className="calendar-overflow"><div ref={calendarElement} className="calendar-canvas" /></div>
      <ul className="calendar-event-list" aria-label="Detalle de eventos del horario">
        {events.map((event, index) => (
          <li key={`${event.extendedProps.code}-${event.extendedProps.group}-${event.extendedProps.type}-${event.daysOfWeek[0]}-${event.startTime}-${index}`}>
            <span className="event-swatch" style={{ backgroundColor: event.backgroundColor }} />
            <span><strong>{event.title}</strong><small>{timeRange(event)} · Aula: {event.extendedProps.room}{event.extendedProps.conflict ? ' · Conflicto de horario' : ''}</small></span>
          </li>
        ))}
      </ul>
    </section>
  );
}
