import type {
  Attempt,
  AttemptResult,
  AttemptState,
  KardexState,
  KardexStatus,
} from './types';

const MINIMUM_PASSING_GRADE = 51;

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const valueOf = (record: UnknownRecord, ...keys: string[]): unknown => {
  for (const key of keys) {
    if (Object.hasOwn(record, key) && record[key] !== '' && record[key] != null) {
      return record[key];
    }
  }
  return null;
};

const text = (value: unknown): string | null => {
  if (value == null) return null;
  const normalized = String(value).trim();
  return normalized || null;
};

const number = (value: unknown): number | null => {
  if (value == null || value === '') return null;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
};

const integer = (value: unknown): number | null => {
  const normalized = number(value);
  return normalized == null ? null : Math.trunc(normalized);
};

const result = (value: unknown): AttemptResult | null => {
  const normalized = text(value)?.toUpperCase();
  return normalized === 'APR' || normalized === 'REP' || normalized === 'ABA'
    ? normalized
    : null;
};

const periodFor = (term: number | null): string | null => ({
  1: 'semestre regular 1',
  2: 'semestre regular 2',
  3: 'intersemestral verano',
  4: 'intersemestral invierno',
})[String(term)] ?? null;

const modalityFor = (mode: string | null): string | null => ({
  N: 'Normal',
  E: 'Mesa',
})[mode ?? ''] ?? null;

const normalizeAttempt = (input: unknown): Attempt => {
  const raw = isRecord(input) ? input : { result: input };
  const term = integer(valueOf(raw, 'term', 'gestion', 'Gestion'));
  const mode = text(valueOf(raw, 'mode', 'md', 'MD'))?.toUpperCase() ?? null;

  return {
    year: integer(valueOf(raw, 'year', 'anio', 'Anio', 'Año')),
    term,
    final: number(valueOf(raw, 'final', 'nfin', 'nFIN', 'NFIN')),
    result: result(valueOf(raw, 'result', 'rfin', 'RFIN')),
    mode,
    modality: text(valueOf(raw, 'modality', 'modalidad')) ?? modalityFor(mode),
    period: text(valueOf(raw, 'period', 'tipo_periodo')) ?? periodFor(term),
    number: (valueOf(raw, 'number', 'nro', 'Nro') as string | number | null) ?? null,
    level: text(valueOf(raw, 'level', 'nivel', 'Nivel')),
    type: text(valueOf(raw, 'type', 'tp', 'TP')),
    validation: text(valueOf(raw, 'validation', 'cv', 'CV')),
    group: text(valueOf(raw, 'group', 'gr', 'GR')),
    practicalGroup: text(valueOf(raw, 'practicalGroup', 'grpr', 'GRPR')),
    t1: number(valueOf(raw, 't1', 'T1')),
    t2: number(valueOf(raw, 't2', 'T2')),
    t3: number(valueOf(raw, 't3', 'T3')),
    p1: number(valueOf(raw, 'p1', 'P1')),
    p2: number(valueOf(raw, 'p2', 'P2')),
    exam: number(valueOf(raw, 'exam', 'ef', 'EF')),
    secondExam: number(valueOf(raw, 'secondExam', '2da')),
    tableMode: text(valueOf(raw, 'tableMode', 'mdTI', 'mdti', 'MDTI')),
    generalExam: number(valueOf(raw, 'generalExam', 'eg', 'EG')),
  };
};

const codeOf = (record: UnknownRecord): string | null =>
  text(valueOf(record, 'code', 'codigo', 'codigo_sis', 'Codigo SIS'));

const configurationOf = (input: UnknownRecord): Pick<KardexState, 'currentYear' | 'currentTerm'> => {
  const configuration = isRecord(input.configuration)
    ? input.configuration
    : isRecord(input.configuracion)
      ? input.configuracion
      : input;
  return {
    currentYear: integer(valueOf(configuration, 'currentYear', 'anio_actual')),
    currentTerm: integer(valueOf(configuration, 'currentTerm', 'gestion_actual')),
  };
};

export function normalizeAttempts(input: unknown): KardexState {
  const attempts: Record<string, Attempt[]> = {};
  const add = (code: string | null, values: unknown): void => {
    if (!code) return;
    const source = Array.isArray(values) ? values : [];
    attempts[code.trim()] = source.map(normalizeAttempt);
  };

  if (Array.isArray(input)) {
    for (const item of input) {
      if (!isRecord(item)) continue;
      const code = codeOf(item);
      if (!code) continue;
      (attempts[code] ??= []).push(normalizeAttempt(item));
    }
    return { attempts, currentYear: null, currentTerm: null };
  }

  if (!isRecord(input)) return { attempts, currentYear: null, currentTerm: null };

  if (Array.isArray(input.subjects)) {
    for (const item of input.subjects) {
      if (isRecord(item)) add(codeOf(item), item.attempts ?? item.intentos);
    }
  } else {
    const source = isRecord(input.attempts)
      ? input.attempts
      : isRecord(input.intentos)
        ? input.intentos
        : input;
    for (const [code, value] of Object.entries(source)) {
      if (code === 'configuration' || code === 'configuracion') continue;
      if (Array.isArray(value)) add(code, value);
      else if (isRecord(value)) add(code, value.attempts ?? value.intentos);
    }
  }

  return { attempts, ...configurationOf(input) };
}

const statusOf = (attempt: Attempt): Exclude<KardexStatus, 'EN_CURSO' | 'SIN_HISTORIAL'> | null => {
  if (attempt.result === 'APR') return 'APROBADA';
  if (attempt.result === 'REP') return 'REPROBADA';
  if (attempt.result === 'ABA') return 'ABANDONADA';
  if (attempt.final == null) return null;
  return attempt.final >= MINIMUM_PASSING_GRADE ? 'APROBADA' : 'REPROBADA';
};

const attemptList = (input: unknown): Attempt[] => {
  if (Array.isArray(input)) return input.map(normalizeAttempt);
  if (!isRecord(input)) return [];
  if (Array.isArray(input.attempts)) return input.attempts.map(normalizeAttempt);
  const normalized = normalizeAttempts(input);
  return Object.values(normalized.attempts).flat();
};

export function determineAttemptState(
  input: unknown,
  current: { year: number | null; term: number | null } = { year: null, term: null },
): AttemptState {
  const attempts = attemptList(input);
  if (attempts.length === 0) {
    return { status: 'SIN_HISTORIAL', provisional: false, approved: false, latest: null };
  }

  const latest = attempts.reduce((mostRecent, candidate) => {
    const left = [mostRecent.year ?? 0, mostRecent.term ?? 0];
    const right = [candidate.year ?? 0, candidate.term ?? 0];
    return right[0]! > left[0]! || (right[0] === left[0] && right[1]! > left[1]!)
      ? candidate
      : mostRecent;
  });

  if (attempts.some((attempt) => statusOf(attempt) === 'APROBADA')) {
    return { status: 'APROBADA', provisional: false, approved: true, latest };
  }

  const latestStatus = statusOf(latest);
  const isCurrent = latest.year != null
    && latest.term != null
    && latest.year === current.year
    && latest.term === current.term;
  if (isCurrent) {
    return {
      status: latestStatus ?? 'EN_CURSO',
      provisional: true,
      approved: false,
      latest,
    };
  }

  return {
    status: latestStatus ?? 'SIN_HISTORIAL',
    provisional: false,
    approved: false,
    latest,
  };
}

export function stateForCode(code: string, kardex: KardexState): AttemptState {
  return determineAttemptState(kardex.attempts[String(code)] ?? [], {
    year: kardex.currentYear,
    term: kardex.currentTerm,
  });
}
