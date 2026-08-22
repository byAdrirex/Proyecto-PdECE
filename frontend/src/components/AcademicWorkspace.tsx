import { useMemo, useState, type ChangeEvent } from 'react';

import catalogFixture from '../data/catalog.json';
import objectivesFixture from '../data/objectives.json';
import { progressSummary, subjectState } from '../lib/domain/academic';
import { normalizeAttempts } from '../lib/domain/kardex';
import { createPlan } from '../lib/domain/planner';
import type { Catalog, KardexState, ObjectivesData } from '../lib/domain/types';
import { parseKardexPdf } from '../lib/pdf/kardex-parser';
import { clearWorkspace, loadWorkspace } from '../lib/storage';
import { Button } from './ui/Button';
import { ProgressBar } from './ui/ProgressBar';
import { StatusBadge } from './ui/StatusBadge';
import { useWorkspace } from './useWorkspace';

const catalog = catalogFixture as Catalog;
const objectives = objectivesFixture as ObjectivesData;

export interface AcademicWorkspaceProps {
  view?: 'progress' | 'new' | 'planner';
}

const emptyKardex = (): KardexState => normalizeAttempts({
  attempts: {},
  configuration: { currentYear: 2026, currentTerm: 2 },
});

export function AcademicWorkspace({ view = 'progress' }: AcademicWorkspaceProps) {
  const [workspace, updateWorkspace] = useWorkspace();
  const [manualOpen, setManualOpen] = useState(view === 'planner');
  const [query, setQuery] = useState('');
  const [manualGrades, setManualGrades] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [loadingPdf, setLoadingPdf] = useState(false);
  const kardex = workspace.kardex;
  const selectedObjectiveIds = [...workspace.activeMentions, ...workspace.activeTechnicians];
  const summary = useMemo(
    () => progressSummary(catalog, kardex ?? emptyKardex(), objectives, selectedObjectiveIds),
    [kardex, selectedObjectiveIds.join('|')],
  );
  const registered = useMemo(
    () => Object.keys(kardex?.attempts ?? {}).flatMap((code) => {
      const subject = catalog.subjects.find((candidate) => candidate.code === code);
      return subject ? [{ subject, academic: subjectState(code, catalog, kardex ?? emptyKardex()) }] : [];
    }).sort((left, right) => left.subject.name.localeCompare(right.subject.name, 'es')),
    [kardex],
  );
  const matches = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('es');
    if (!normalized) return [];
    return catalog.subjects
      .filter((subject) => subject.code.includes(normalized) || subject.name.toLocaleLowerCase('es').includes(normalized))
      .filter((subject) => !kardex?.attempts[subject.code])
      .slice(0, 8);
  }, [query, kardex]);
  const trajectoryProgress = useMemo(() => [
    ...Object.entries(summary.mentions).flatMap(([id, category]) => {
      const objective = objectives.mentions.find((candidate) => candidate.id === id);
      return objective ? [{ objective, category }] : [];
    }),
    ...Object.entries(summary.technicians).flatMap(([id, category]) => {
      const objective = objectives.technicians.find((candidate) => candidate.id === id);
      return objective ? [{ objective, category }] : [];
    }),
  ], [summary.mentions, summary.technicians]);

  const replaceKardex = (nextKardex: KardexState, success: string): void => {
    updateWorkspace((current) => ({
      ...current,
      kardex: nextKardex,
      mode: 'academic',
      plan: current.plan?.mode === 'academic'
        ? current.plan
        : createPlan('academic', 2026, 2),
    }));
    setMessage(success);
  };

  const addManualGrade = (code: string, name: string): void => {
    const final = Number(manualGrades[code]);
    if (manualGrades[code]?.trim() === '' || !Number.isFinite(final) || final < 0 || final > 100) {
      setMessage('Ingresa una nota final valida entre 0 y 100.');
      return;
    }
    const current = kardex ?? emptyKardex();
    const result = final >= 51 ? 'APR' : 'REP';
    const next = normalizeAttempts({
      attempts: {
        ...current.attempts,
        [code]: [{
          year: current.currentYear ?? 2026,
          term: current.currentTerm ?? 2,
          final,
          result,
          mode: 'N',
        }],
      },
      configuration: { currentYear: current.currentYear ?? 2026, currentTerm: current.currentTerm ?? 2 },
    });
    replaceKardex(next, `${name} se registro como ${result === 'APR' ? 'aprobada' : 'reprobada'}.`);
    setManualGrades((grades) => {
      const updated = { ...grades };
      delete updated[code];
      return updated;
    });
    setQuery('');
  };

  const removeSubject = (code: string, name: string): void => {
    const nextAttempts = { ...(kardex?.attempts ?? {}) };
    delete nextAttempts[code];
    const next = normalizeAttempts({
      attempts: nextAttempts,
      configuration: {
        currentYear: kardex?.currentYear ?? 2026,
        currentTerm: kardex?.currentTerm ?? 2,
      },
    });
    replaceKardex(next, `${name} se elimino del Kardex.`);
  };

  const readPdf = async (event: ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoadingPdf(true);
    setMessage(null);
    const result = await parseKardexPdf(file);
    setLoadingPdf(false);
    if (!result.ok) {
      setMessage(`${result.error} Puedes continuar con el registro manual.`);
      return;
    }
    replaceKardex(result.kardex, `Kardex cargado: ${result.rowCount} registros reconocidos.`);
  };

  if (view === 'new') {
    const reset = (): void => {
      clearWorkspace();
      const fresh = loadWorkspace();
      updateWorkspace({ ...fresh, mode: 'manual', plan: createPlan('manual', 2026, 2) });
      window.location.assign('/horario');
    };
    return (
      <section className="narrow-page surface student-new">
        <p className="eyebrow">Inicio rápido</p>
        <h1>Estudiante Nuevo</h1>
        <p>Arma tu horario sin historial académico previo. El planificador manual no verifica prerrequisitos.</p>
        <Button onClick={reset}>Comenzar planificación manual</Button>
        <a className="button button--secondary" href="/horario">← Volver y cargar mi Kardex</a>
        <div className="level-pills" aria-label="Niveles disponibles">
          {catalog.levels.map((level) => <span key={level}>Nivel {level}</span>)}
        </div>
      </section>
    );
  }

  return (
    <section className={`academic-workspace${view === 'planner' ? ' academic-workspace--compact' : ''}`}>
      <header className="page-heading">
        <p className="eyebrow">Tu información permanece en este navegador</p>
        <h1>{view === 'planner' ? 'Carga tu Kardex' : 'Mi progreso'}</h1>
        <p>Importa tu reporte SISS o registra materias manualmente. Ningún archivo se envía a internet.</p>
      </header>

      <div className="import-grid">
        <label className="import-card">
          <strong>{loadingPdf ? 'Procesando PDF…' : 'Cargar Kardex en PDF'}</strong>
          <span>Máximo 10 MB. El análisis se realiza localmente.</span>
          <input type="file" accept="application/pdf" disabled={loadingPdf} onChange={(event) => void readPdf(event)} />
        </label>
        <button type="button" className="import-card" aria-label="Registro manual" onClick={() => setManualOpen((open) => !open)}>
          <strong>Registro manual</strong>
          <span>Busca una materia y márcala como aprobada.</span>
        </button>
      </div>

      {message && <p className="notice" role="status">{message}</p>}

      {manualOpen && (
        <section className="surface manual-kardex">
          <h2>Agregar materias manualmente</h2>
          <label>
            <span>Materia</span>
            <input
              type="search"
              aria-label="Buscar materia"
              placeholder="Buscar por código o nombre"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {matches.length > 0 && (
            <ul className="search-results">
              {matches.map((subject) => (
                <li key={subject.code}>
                  <span><strong>{subject.name}</strong><small>{subject.code}</small></span>
                  <label className="grade-field">
                    <span>Nota final</span>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      inputMode="numeric"
                      aria-label={`Nota final para ${subject.name}`}
                      value={manualGrades[subject.code] ?? ''}
                      onChange={(event) => setManualGrades((grades) => ({ ...grades, [subject.code]: event.target.value }))}
                    />
                  </label>
                  <Button aria-label={`Registrar ${subject.name}`} onClick={() => addManualGrade(subject.code, subject.name)}>Registrar nota</Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view === 'progress' && (
        <>
          <section className="progress-hero surface">
            <div>
              <p className="eyebrow">Avance de materias obligatorias</p>
              <h2>{summary.required.approved} de {summary.required.total}</h2>
              <p>{summary.required.percentage}% completado · {summary.approvedCredits} créditos aprobados</p>
            </div>
            <ProgressBar value={summary.required.percentage} label="Avance de materias obligatorias" />
          </section>
          <div className="metric-grid">
            <article><span>Obligatorias</span><strong>{summary.required.approved} / {summary.required.total}</strong></article>
            <article><span>No curriculares</span><strong>{summary.nonCurricular.approved} / {summary.nonCurricular.total}</strong></article>
            <article><span>Electivas</span><strong>{summary.electives.approved.length} / {summary.electives.required}</strong></article>
            <article><span>Créditos</span><strong>{summary.approvedCredits}</strong></article>
          </div>
          {trajectoryProgress.length > 0 && (
            <section className="trajectory-progress" aria-labelledby="trajectory-progress-title">
              <div className="section-heading"><h2 id="trajectory-progress-title">Progreso de trayectorias activas</h2><span>{trajectoryProgress.length}</span></div>
              <div className="trajectory-progress__grid">
                {trajectoryProgress.map(({ objective, category }) => (
                  <article className="surface" key={objective.id}>
                    <p className="eyebrow">{objective.kind === 'mention' ? 'Mención' : 'Técnico Superior'}</p>
                    <h3>{objective.name}</h3>
                    <strong>{category.approved} de {category.total}</strong>
                    <ProgressBar value={category.percentage} label={`Progreso de ${objective.name}`} />
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <section className="surface registered-kardex">
        <div className="section-heading"><h2>Materias registradas</h2><span>{registered.length}</span></div>
        {registered.length === 0 ? (
          <p className="empty-state">Todavia no registraste materias. Usa el PDF o el registro manual para comenzar.</p>
        ) : (
          <div className="table-scroll"><table><thead><tr><th>Materia</th><th>Estado</th><th>Acción</th></tr></thead><tbody>
            {registered.map(({ subject, academic }) => (
              <tr key={subject.code}>
                <td><strong>{subject.name}</strong><small>{subject.code}</small></td>
                <td><StatusBadge status={academic.status} /></td>
                <td><Button variant="danger" aria-label={`Eliminar ${subject.name}`} onClick={() => removeSubject(subject.code, subject.name)}>Eliminar materia</Button></td>
              </tr>
            ))}
          </tbody></table></div>
        )}
      </section>

      <nav className="action-row" aria-label="Continuar planificación">
        <a className="button button--secondary" href="/malla">Ver malla curricular</a>
        <a className="button button--primary" href="/horario">Armar mi horario</a>
      </nav>
    </section>
  );
}
