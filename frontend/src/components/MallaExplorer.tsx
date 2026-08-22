import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import catalogFixture from '../data/catalog.json';
import objectivesFixture from '../data/objectives.json';
import offerFixture from '../data/offer.json';
import { buildMallaModel } from '../lib/domain/curriculum';
import { normalizeAttempts } from '../lib/domain/kardex';
import { applyObjectiveSelections } from '../lib/domain/objectives';
import type { Catalog, MallaSubject, ObjectivesData, Offer } from '../lib/domain/types';
import { Button } from './ui/Button';
import { StatusBadge } from './ui/StatusBadge';
import { useWorkspace } from './useWorkspace';

const catalog = catalogFixture as Catalog;
const objectives = objectivesFixture as ObjectivesData;
const offer = offerFixture as Offer;

export interface MallaExplorerProps {
  showBackLink?: boolean;
}

export function MallaExplorer({ showBackLink = false }: MallaExplorerProps) {
  const [workspace, updateWorkspace] = useWorkspace();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const lastSubjectTrigger = useRef<HTMLButtonElement>(null);
  const base = useMemo(
    () => buildMallaModel(catalog, workspace.kardex ?? normalizeAttempts([]), offer),
    [workspace.kardex],
  );
  const model = useMemo(
    () => applyObjectiveSelections(base, objectives, {
      mentions: workspace.activeMentions,
      technicians: workspace.activeTechnicians,
    }),
    [base, workspace.activeMentions, workspace.activeTechnicians],
  );
  const selected = selectedCode ? model.subjects[selectedCode] ?? null : null;
  const selectedConnections = useMemo(() => selectedCode
    ? model.connections.filter(({ from, to }) => from === selectedCode || to === selectedCode)
    : [], [model.connections, selectedCode]);
  const related = useMemo(() => selectedCode
    ? new Set([selectedCode, ...selectedConnections.flatMap(({ from, to }) => [from, to])])
    : new Set<string>(), [selectedCode, selectedConnections]);

  const closeDialog = useCallback((): void => {
    setSelectedCode(null);
    lastSubjectTrigger.current?.focus();
  }, []);

  useEffect(() => {
    if (!selectedCode) return;
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') closeDialog();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [closeDialog, selectedCode]);

  const toggleObjective = (id: string, kind: 'mention' | 'technician'): void => {
    updateWorkspace((current) => {
      const key = kind === 'mention' ? 'activeMentions' : 'activeTechnicians';
      const values = current[key].includes(id)
        ? current[key].filter((value) => value !== id)
        : [...current[key], id];
      return { ...current, [key]: values };
    });
  };

  const card = (subject: MallaSubject) => (
    <button
      key={subject.code}
      type="button"
      className={`subject-card subject-card--${subject.status.toLowerCase()}${selected && !related.has(subject.code) ? ' subject-card--dimmed' : ''}`}
      data-subject-code={subject.code}
      onClick={(event) => {
        lastSubjectTrigger.current = event.currentTarget;
        setSelectedCode(subject.code);
      }}
      style={subject.colorGradient ? { background: subject.colorGradient } : undefined}
    >
      <span className="subject-card__code">{subject.code}</span>
      <strong>{subject.name}</strong>
      <span>{subject.credits ?? 0} cr. · {subject.hours ?? 0} h.</span>
    </button>
  );

  const subjectLink = (code: string) => {
    const subject = model.subjects[code];
    return subject ? (
      <button type="button" className="text-link" onClick={() => setSelectedCode(code)} key={code}>
        {subject.name} ({subject.code})
      </button>
    ) : null;
  };

  return (
    <section className="malla-shell" aria-labelledby="malla-title">
      {showBackLink && <a className="back-link" href="/">← Volver al inicio</a>}
      <header className="page-heading">
        <p className="eyebrow">Carrera de Economía · UMSS</p>
        <h1 id="malla-title">Malla curricular</h1>
        <p>Explora materias, prerrequisitos y trayectorias del plan de estudios.</p>
      </header>

      <nav className="quick-links" aria-label="Acciones académicas">
        <a href="/progreso">Mi progreso</a>
        <a href="/horario">Quiero armar mi horario</a>
        <a href="/guia">Guía</a>
        <a href="/calendario-academico">Calendario Académico</a>
      </nav>

      <div className="status-legend" aria-label="Leyenda de estados">
        {(['APROBADA', 'EN_CURSO', 'DISPONIBLE', 'BLOQUEADA', 'REPROBADA'] as const)
          .map((status) => <StatusBadge status={status} key={status} />)}
      </div>

      <div className="semester-scroll" aria-label="Nueve semestres de la malla">
        <div className="semester-grid">
          {model.levels.map((level) => (
            <section className="semester-column" data-semester={level} key={level}>
              <h2>{model.levelLabels[level]} Semestre</h2>
              {model.areas.map((area) => {
                const subjects = model.cells.find((cell) => cell.level === level && cell.area === area)?.subjects ?? [];
                return subjects.length > 0 ? (
                  <div className="area-cell" key={area}>
                    <h3>{area}</h3>
                    {subjects.map(card)}
                  </div>
                ) : null;
              })}
              {(model.integratedByLevel[level] ?? []).length > 0 && (
                <div className="area-cell area-cell--elective">
                  <h3>Trayectorias activas</h3>
                  {model.integratedByLevel[level]!.map(card)}
                </div>
              )}
            </section>
          ))}
        </div>
      </div>

      <section className="surface compact-requirements">
        <h2>Talleres Complementarios e Inglés</h2>
        <div className="compact-subjects">{[...model.workshops, ...model.english].map(card)}</div>
      </section>

      <section className="objective-section" aria-labelledby="objectives-title">
        <div>
          <p className="eyebrow">Personaliza la malla</p>
          <h2 id="objectives-title">Técnicos y Menciones</h2>
        </div>
        <div className="objective-grid">
          {objectives.technicians.map((objective) => (
            <button
              type="button"
              key={objective.id}
              aria-pressed={workspace.activeTechnicians.includes(objective.id)}
              aria-label={`${workspace.activeTechnicians.includes(objective.id) ? 'Desactivar' : 'Activar'} ${objective.name}`}
              onClick={() => toggleObjective(objective.id, 'technician')}
            >
              <span>Técnico Superior</span><strong>{objective.name}</strong>
              <small>{objective.subjectCodes.length} materias</small>
            </button>
          ))}
          {objectives.mentions.map((objective) => (
            <button
              type="button"
              key={objective.id}
              aria-pressed={workspace.activeMentions.includes(objective.id)}
              aria-label={`${workspace.activeMentions.includes(objective.id) ? 'Desactivar' : 'Activar'} ${objective.name}`}
              onClick={() => toggleObjective(objective.id, 'mention')}
            >
              <span>Mención</span><strong>{objective.name}</strong>
              <small>{objective.subjectCodes.length} materias</small>
            </button>
          ))}
        </div>
      </section>

      {selected && (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && closeDialog()}>
          <section role="dialog" aria-modal="true" aria-label={`Detalle de ${selected.name}`} className="subject-dialog">
            <header>
              <div><p className="eyebrow">SIS {selected.code}</p><h2>{selected.name}</h2></div>
              <Button ref={closeButton} variant="quiet" aria-label="Cerrar detalle" onClick={closeDialog}>×</Button>
            </header>
            <div className="subject-dialog__meta">
              <StatusBadge status={selected.status} />
              <span>{selected.area}</span><span>{selected.credits ?? '—'} créditos</span><span>{selected.hours ?? '—'} horas</span>
            </div>
            {selected.memberships.length > 0 && <p>Pertenece a: {selected.memberships.map(({ name }) => name).join(', ')}</p>}
            <div className="relation-grid">
              <div><h3>Prerrequisitos</h3>{selected.prerequisites.length ? selected.prerequisites.map(subjectLink) : <p>No requiere prerrequisitos</p>}</div>
              <div><h3>Materias que habilita</h3>{selected.dependents.length ? selected.dependents.map(subjectLink) : <p>No habilita otras materias</p>}</div>
            </div>
            <section className="connection-list" aria-label={`Conexiones de ${selected.name}`}>
              <h3>Conexiones de prerrequisitos</h3>
              <ul>
                {selectedConnections.map(({ from, to }) => (
                  <li key={`${from}-${to}`}>
                    {model.subjects[from]?.name ?? from} → {model.subjects[to]?.name ?? to}
                  </li>
                ))}
              </ul>
            </section>
            {selected.offered && <a className="button button--primary" href={`/horario?materia=${selected.code}`}>Ver {selected.groupCount} grupos disponibles</a>}
          </section>
        </div>
      )}
    </section>
  );
}
