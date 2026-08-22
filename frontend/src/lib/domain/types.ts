export type AttemptResult = 'APR' | 'REP' | 'ABA';

export type KardexStatus =
  | 'APROBADA'
  | 'REPROBADA'
  | 'ABANDONADA'
  | 'EN_CURSO'
  | 'SIN_HISTORIAL';

export type AcademicStatus =
  | KardexStatus
  | 'SIN_PRERREQUISITOS'
  | 'DISPONIBLE'
  | 'BLOQUEADA';

export interface Attempt {
  year: number | null;
  term: number | null;
  final: number | null;
  result: AttemptResult | null;
  mode: string | null;
  modality: string | null;
  period: string | null;
  number: string | number | null;
  level: string | null;
  type: string | null;
  validation: string | null;
  group: string | null;
  practicalGroup: string | null;
  t1: number | null;
  t2: number | null;
  t3: number | null;
  p1: number | null;
  p2: number | null;
  exam: number | null;
  secondExam: number | null;
  tableMode: string | null;
  generalExam: number | null;
}

export interface KardexState {
  attempts: Record<string, Attempt[]>;
  currentYear: number | null;
  currentTerm: number | null;
}

export interface AttemptState {
  status: KardexStatus;
  provisional: boolean;
  approved: boolean;
  latest: Attempt | null;
}

export interface Subject {
  code: string;
  name: string;
  level: string | null;
  area: string;
  credits: number | null;
  hours: number | null;
  abbreviation: string | null;
  type: string;
  prerequisites: string[];
  dependents: string[];
}

export interface CatalogEdge {
  from: string;
  to: string;
}

export interface Catalog {
  subjects: Subject[];
  levels: string[];
  areas: string[];
  edges: CatalogEdge[];
}

export interface ScheduleBlock {
  day: string | null;
  start: string | null;
  end: string | null;
  room: string | null;
}

export interface OfferAuxiliary {
  name: string | null;
  schedule: ScheduleBlock[];
}

export interface OfferGroup {
  code: string;
  name: string | null;
  level: string | null;
  group: string | null;
  instructor: string | null;
  schedule: ScheduleBlock[];
  auxiliaries: OfferAuxiliary[];
}

export interface Offer {
  year: number;
  term: number;
  termType: string;
  totalSubjects: number;
  totalGroups: number;
  groups: OfferGroup[];
  groupsBySubject: Record<string, OfferGroup[]>;
}

export interface Objective {
  id: string;
  kind: 'mention' | 'technician';
  name: string;
  subjectCodes: string[];
}

export interface ObjectiveSubstitution {
  mentionId: string;
  original: string;
  replacement: string;
}

export interface ObjectivesData {
  trajectories: Objective[];
  mentions: Objective[];
  technicians: Objective[];
  substitutions: ObjectiveSubstitution[];
  licenciaturaElectiveRequirement: number;
}

export interface AcademicState {
  code: string;
  status: AcademicStatus;
  kardexStatus: KardexStatus;
  provisional: boolean;
  missingPrerequisites: string[];
  offered: boolean | null;
  offerStatus: 'OFERTADA' | 'NO_OFERTADA' | null;
  groups: OfferGroup[];
}

export interface ProgressCategory {
  total: number;
  approved: number;
  inProgress: number;
  pending: number;
  percentage: number;
  credits: number;
  approvedCredits: number;
  approvedCodes: string[];
  inProgressCodes: string[];
  pendingCodes: string[];
}

export interface ElectiveProgress {
  required: number;
  approved: string[];
  pending: string[];
  remaining: number;
  completed: boolean;
}

export interface ProgressSummary {
  required: ProgressCategory;
  nonCurricular: ProgressCategory;
  electives: ElectiveProgress;
  mentions: Record<string, ProgressCategory>;
  technicians: Record<string, ProgressCategory>;
  totalCredits: number;
  approvedCredits: number;
}

export interface ObjectiveMembership {
  id: string;
  kind: Objective['kind'];
  name: string;
  color: string;
}

export interface MallaSubject extends Subject {
  areaRaw: string;
  status: AcademicStatus;
  missingPrerequisites: string[];
  provisional: boolean;
  offered: boolean | null;
  groupCount: number;
  memberships: ObjectiveMembership[];
  colorGradient?: string;
  replaces?: Array<{ code: string; name: string }>;
}

export interface MallaCell {
  level: string;
  area: string;
  subjects: MallaSubject[];
}

export interface MallaModel {
  subjects: Record<string, MallaSubject>;
  levels: string[];
  levelLabels: Record<string, string>;
  areas: string[];
  cells: MallaCell[];
  workshops: MallaSubject[];
  english: MallaSubject[];
  connections: CatalogEdge[];
  totalSubjects: number;
  totalRequired: number;
  activeMentions: string[];
  activeTechnicians: string[];
  substitutions: Record<string, string>;
  integrated: Record<string, MallaSubject>;
  integratedByLevel: Record<string, MallaSubject[]>;
}
