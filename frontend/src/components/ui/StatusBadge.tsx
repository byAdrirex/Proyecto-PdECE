import type { AcademicStatus } from '../../lib/domain/types';

const labels: Record<AcademicStatus, string> = {
  APROBADA: 'Aprobada',
  REPROBADA: 'Reprobada',
  ABANDONADA: 'Abandonada',
  EN_CURSO: 'En curso',
  SIN_HISTORIAL: 'Sin historial',
  SIN_PRERREQUISITOS: 'Sin prerrequisitos',
  DISPONIBLE: 'Disponible',
  BLOQUEADA: 'Bloqueada',
};

export function StatusBadge({ status }: { status: AcademicStatus }) {
  return <span className={`status status--${status.toLowerCase()}`}>{labels[status]}</span>;
}
