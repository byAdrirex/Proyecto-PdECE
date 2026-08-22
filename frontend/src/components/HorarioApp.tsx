import { useEffect, useMemo, useState } from 'react';

import catalogFixture from '../data/catalog.json';
import offerFixture from '../data/offer.json';
import { subjectState } from '../lib/domain/academic';
import { normalizeAttempts } from '../lib/domain/kardex';
import {
  createPlan,
  detectConflicts,
  planSummary,
  recommendGroup,
  removeGroup,
  selectGroup,
  type PlannerGroup,
  type PlannerMode,
  type PlannerPlan,
} from '../lib/domain/planner';
import type { Catalog, Offer, Subject } from '../lib/domain/types';
import { AcademicWorkspace } from './AcademicWorkspace';
import { CalendarView } from './CalendarView';
import { Button } from './ui/Button';
import { StatusBadge } from './ui/StatusBadge';
import { useWorkspace } from './useWorkspace';

const catalog = catalogFixture as Catalog;
const offer = offerFixture as Offer;
const emptyKardex = normalizeAttempts([]);
const dayNames: Record<string, string> = {
  LU: 'Lunes', MA: 'Martes', MI: 'Miércoles', JU: 'Jueves', VI: 'Viernes', SA: 'Sábado',
};

export interface HorarioAppProps {
  calendarOnly?: boolean;
}

const modePlan = (mode: PlannerMode): PlannerPlan => createPlan(mode, offer.year, offer.term);
const formatHours = (hours: number): string => Number.isInteger(hours) ? String(hours) : hours.toFixed(1);

export function HorarioApp({ calendarOnly = false }: HorarioAppProps) {
  const [workspace, updateWorkspace] = useWorkspace();
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState<string | null>(null);
  const [openSubjectCode, setOpenSubjectCode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const plan = workspace.plan;

  useEffect(() => {
    if (workspace.mode === 'academic' && workspace.kardex && !workspace.plan) {
      updateWorkspace((current) => ({ ...current, plan: modePlan('academic') }));
    }
  }, [workspace.mode, workspace.kardex, workspace.plan, updateWorkspace]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const requestedMode = params.get('modo');
    if (!workspace.mode && (requestedMode === 'manual' || requestedMode === 'academic')) {
      if (requestedMode === 'manual') chooseMode('manual');
      else updateWorkspace((current) => ({ ...current, mode: 'academic', plan: current.kardex ? modePlan('academic') : null }));
    }
    const requestedSubject = params.get('materia');
    if (requestedSubject && catalog.subjects.some(({ code }) => code === requestedSubject)) {
      setOpenSubjectCode(requestedSubject);
      setQuery(requestedSubject);
    }
  // URL parameters are initial hydration input only.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chooseMode = (mode: PlannerMode): void => {
    updateWorkspace((current) => ({
      ...current,
      mode,
      plan: mode === 'academic' && !current.kardex ? null : modePlan(mode),
      ...(mode === 'manual' ? { kardex: current.kardex } : {}),
    }));
    setMessage(null);
  };

  const offeredSubjects = useMemo(() => catalog.subjects.filter((subject) =>
    (offer.groupsBySubject[subject.code]?.length ?? 0) > 0), []);
  const visibleSubjects = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('es');
    return offeredSubjects
      .filter((subject) => !level || subject.level === level)
      .filter((subject) => !normalized || subject.code.includes(normalized) || subject.name.toLocaleLowerCase('es').includes(normalized))
      .slice(0, normalized ? 20 : 12);
  }, [level, offeredSubjects, query]);
  const openSubject = openSubjectCode
    ? catalog.subjects.find((subject) => subject.code === openSubjectCode) ?? null
    : null;
  const summary = plan ? planSummary(plan) : null;

  const persistPlan = (nextPlan: PlannerPlan): void => updateWorkspace((current) => ({
    ...current,
    mode: nextPlan.mode,
    plan: nextPlan,
  }));

  const select = (subject: Subject, group: PlannerGroup): void => {
    if (!plan) return;
    const academic = subjectState(subject.code, catalog, workspace.kardex ?? emptyKardex, offer);
    const result = selectGroup(plan, group, { academic, prerequisites: subject.prerequisites });
    if (!result.ok) {
      setMessage(result.message);
      return;
    }
    persistPlan(result.plan);
    setMessage(`${subject.name}, grupo ${group.group ?? '?'}, agregado al horario.`);
  };

  const remove = (subject: Subject, group: PlannerGroup): void => {
    if (!plan || !group.group) return;
    const result = removeGroup(plan, subject.code, group.group);
    if (!result.ok) {
      setMessage(result.message);
      return;
    }
    persistPlan(result.plan);
    setMessage(`${subject.name}, grupo ${group.group}, eliminado del horario.`);
  };

  const toggleAuxiliary = (): void => {
    if (!plan) return;
    const next: PlannerPlan = { ...plan, includeAuxiliary: !plan.includeAuxiliary, conflicts: [] };
    next.conflicts = detectConflicts(next, next.includeAuxiliary);
    persistPlan(next);
  };

  if (calendarOnly) {
    const calendarPlan = plan ?? modePlan('manual');
    return (
      <section className="planner-calendar-page">
        <a className="back-link" href="/horario">← Volver al planificador</a>
        <header className="page-heading"><p className="eyebrow">Vista ampliada</p><h1>Calendario de mi horario</h1></header>
        <CalendarView plan={calendarPlan} />
      </section>
    );
  }

  if (!workspace.mode) {
    return (
      <section className="mode-picker surface narrow-page">
        <p className="eyebrow">Planificador 2026-2</p>
        <h1>¿Cómo quieres armar tu horario?</h1>
        <p>Con Kardex verificamos tu historial. En modo manual puedes explorar libremente y verás advertencias de prerrequisitos.</p>
        <Button onClick={() => chooseMode('academic')}>Planificar con Kardex</Button>
        <Button variant="secondary" onClick={() => chooseMode('manual')}>Planificar sin Kardex</Button>
        <a href="/nuevo">Soy estudiante nuevo</a>
      </section>
    );
  }

  if (workspace.mode === 'academic' && !workspace.kardex) {
    return (
      <section>
        <div className="planner-toolbar"><Button variant="quiet" onClick={() => updateWorkspace((current) => ({ ...current, mode: null, plan: null }))}>← Cambiar modo</Button></div>
        <AcademicWorkspace view="planner" />
      </section>
    );
  }

  if (!plan) return null;

  const selectedLabel = `${summary?.selectedGroupCount ?? 0} ${(summary?.selectedGroupCount ?? 0) === 1 ? 'materia seleccionada' : 'materias seleccionadas'}`;
  const conflictLabel = `${summary?.conflictCount ?? 0} ${(summary?.conflictCount ?? 0) === 1 ? 'conflicto de horario' : 'conflictos de horario'}`;

  return (
    <section className="planner-app">
      <header className="page-heading planner-heading">
        <div><p className="eyebrow">Oferta académica {offer.year}-{offer.term}</p><h1>Arma tu horario</h1><p>Selecciona materias y compara grupos. Los cambios se guardan automáticamente.</p></div>
        <div className="planner-toolbar"><Button variant="quiet" onClick={() => updateWorkspace((current) => ({ ...current, mode: null, plan: null }))}>Cambiar modo</Button><a href="/malla">Ver malla</a></div>
      </header>
      {message && <p className="notice" role="status">{message}</p>}

      <div className="planner-layout">
        <aside className="planner-browser surface">
          <label><span>Buscar materia</span><input aria-label="Buscar materia para horario" type="search" placeholder="Código o nombre" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
          <div className="level-filter" aria-label="Filtrar por nivel">
            <Button variant={level === null ? 'primary' : 'quiet'} onClick={() => setLevel(null)}>Todos</Button>
            {catalog.levels.map((candidate) => <Button variant={level === candidate ? 'primary' : 'quiet'} key={candidate} onClick={() => setLevel(level === candidate ? null : candidate)}>Nivel {candidate}</Button>)}
          </div>
          <div className="subject-results">
            {visibleSubjects.map((subject) => {
              const academic = subjectState(subject.code, catalog, workspace.kardex ?? emptyKardex, offer);
              return (
                <article key={subject.code} className={openSubjectCode === subject.code ? 'is-open' : ''}>
                  <div><strong>{subject.name}</strong><small>{subject.code} · Nivel {subject.level}</small>{plan.mode === 'academic' && <StatusBadge status={academic.status} />}</div>
                  <Button variant="quiet" aria-label={`Ver grupos de ${subject.name}`} onClick={() => setOpenSubjectCode(openSubjectCode === subject.code ? null : subject.code)}>Grupos</Button>
                </article>
              );
            })}
          </div>

          {openSubject && (
            <section className="group-panel">
              <h2>{openSubject.name}</h2>
              {openSubject.prerequisites.length > 0 && <p className="warning"><strong>Prerrequisitos:</strong> {openSubject.prerequisites.join(', ')}{plan.mode === 'manual' && ' · En modo manual no se verifica tu historial académico.'}</p>}
              <div className="group-list">
                {(offer.groupsBySubject[openSubject.code] ?? []).map((group) => {
                  const selected = plan.selectedGroups.some((candidate) => candidate.code === group.code && candidate.group === group.group);
                  const recommendation = recommendGroup(group, plan, subjectState(openSubject.code, catalog, workspace.kardex ?? emptyKardex, offer));
                  return (
                    <article className={selected ? 'group-card group-card--selected' : 'group-card'} key={`${group.code}-${group.group}`}>
                      <header><span>Grupo {group.group ?? '?'}</span>{group.auxiliaries.length > 0 && <small>AUX disponible</small>}</header>
                      <p><strong>{group.instructor ?? 'Docente por designar'}</strong></p>
                      <ul>{group.schedule.map((block, index) => <li key={`${block.day}-${block.start}-${index}`}>{block.day ?? '—'} {block.start ?? '—'}–{block.end ?? '—'} · {block.room ?? 'Sin aula'}</li>)}</ul>
                      <p className={`recommendation recommendation--${recommendation.label.toLowerCase()}`}><strong>{recommendation.label} · {recommendation.score}/100</strong><span>{recommendation.comment}</span></p>
                      {selected ? (
                        <Button variant="danger" aria-label={`Quitar ${openSubject.name} grupo ${group.group}`} onClick={() => remove(openSubject, group)}>Quitar grupo</Button>
                      ) : (
                        <Button aria-label={`Agregar grupo ${group.group} de ${openSubject.name}`} onClick={() => select(openSubject, group)}>Agregar grupo</Button>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          )}
        </aside>

        <div className="planner-main">
          <CalendarView plan={plan} />
          <aside className="selection-summary surface" aria-label="Resumen de selección">
            <div className="section-heading"><h2>Mi selección</h2><a href="/horario/calendario">Ver calendario completo</a></div>
            <div className="metric-grid metric-grid--planner">
              <article><strong>{selectedLabel}</strong></article>
              <article><strong>{formatHours(summary?.weeklyHours ?? 0)} horas semanales</strong></article>
              <article className={(summary?.conflictCount ?? 0) > 0 ? 'metric--danger' : ''}><strong>{conflictLabel}</strong></article>
            </div>
            <p className="limit-copy">Límite recomendado: {summary?.limits.normalUsed}/{summary?.limits.normalMax} normales · {summary?.limits.mesaUsed}/{summary?.limits.mesaMax} mesa</p>
            {plan.selectedGroups.length === 0 ? <p className="empty-state">No has seleccionado materias aún.</p> : (
              <ul className="selected-groups">{plan.selectedGroups.map((group) => {
                const subject = catalog.subjects.find(({ code }) => code === group.code);
                if (!subject) return null;
                return <li key={`${group.code}-${group.group}`}><span><strong>{subject.name}</strong><small>Grupo {group.group} · {group.instructor}</small></span><Button variant="danger" aria-label={`Quitar ${subject.name} grupo ${group.group}`} onClick={() => remove(subject, group)}>×</Button></li>;
              })}</ul>
            )}
            {(summary?.warnings.length ?? 0) > 0 && <div className="warning-list"><h3>Advertencias</h3>{summary?.warnings.map((warning, index) => <p key={`${warning.code}-${warning.group}-${index}`}>{warning.message}</p>)}</div>}
            {(summary?.conflicts.length ?? 0) > 0 && <div className="conflict-list"><h3>{conflictLabel}</h3>{summary?.conflicts.map((conflict, index) => {
              const left = catalog.subjects.find(({ code }) => code === conflict.subject1)?.name ?? conflict.subject1;
              const right = catalog.subjects.find(({ code }) => code === conflict.subject2)?.name ?? conflict.subject2;
              return <p key={`${conflict.subject1}-${conflict.subject2}-${index}`}><strong>{left} G{conflict.group1} ↔ {right} G{conflict.group2}</strong><span>{dayNames[conflict.day] ?? conflict.day} {conflict.start1}–{conflict.end1}</span></p>;
            })}</div>}
            <div className="aux-toggle"><span>Mostrar horarios de auxiliares</span><button type="button" role="switch" aria-checked={plan.includeAuxiliary} aria-label="Mostrar horarios de auxiliares" onClick={toggleAuxiliary}><span /></button></div>
          </aside>
        </div>
      </div>
    </section>
  );
}
