import { normalizeAttempts } from '../domain/kardex';
import type { KardexState } from '../domain/types';
import { getDocument } from './pdf-worker';

const maximumPdfBytes = 10 * 1024 * 1024;
const pdfSignature = '%PDF';

type ParseErrorCode =
  | 'empty'
  | 'too_large'
  | 'invalid_type'
  | 'invalid_signature'
  | 'malformed'
  | 'unrecognized';

export type ParseResult =
  | { ok: true; kardex: KardexState; rowCount: number }
  | { ok: false; code: ParseErrorCode; error: string };

type KardexColumn =
  | 'number'
  | 'year'
  | 'term'
  | 'code'
  | 'level'
  | 'type'
  | 'mode'
  | 'validation'
  | 'group'
  | 'practicalGroup'
  | 't1'
  | 't2'
  | 't3'
  | 'p1'
  | 'p2'
  | 'exam'
  | 'secondExam'
  | 'tableMode'
  | 'generalExam'
  | 'final'
  | 'result';

interface PositionedTextItem {
  str: string;
  transform?: ArrayLike<unknown>;
  hasEOL?: boolean;
}

interface HeaderAnchor {
  x: number;
  column: KardexColumn | null;
}

const headerAliases: Record<KardexColumn, string[]> = {
  number: ['nro', 'n', 'num', 'numero', '#'],
  year: ['anio', 'ano', 'a', 'year'],
  term: ['gestion', 'gest', 'gst', 'g', 'sem', 'semestre'],
  code: ['codigo', 'cod', 'sis', 'codsis'],
  level: ['nivel', 'niv', 'nv'],
  type: ['tp'],
  mode: ['md', 'modalidad'],
  validation: ['cv'],
  group: ['gr'],
  practicalGroup: ['grpr'],
  t1: ['t1'],
  t2: ['t2'],
  t3: ['t3'],
  p1: ['p1'],
  p2: ['p2'],
  exam: ['ef', 'exfinal', 'examenfinal'],
  secondExam: ['2da', 'segunda', 'seg', '2'],
  tableMode: ['mdti', 'mdtl'],
  generalExam: ['eg', 'gracia'],
  final: ['nfin', 'nfinal', 'notafinal', 'nf'],
  result: ['rfin', 'rfinal', 'resultadofinal', 'resultado', 'res'],
};

const normalizedAliases = new Map<string, KardexColumn>(
  Object.entries(headerAliases).flatMap(([column, aliases]) =>
    aliases.map((alias) => [alias, column as KardexColumn] as const),
  ),
);

const failure = (code: ParseErrorCode, error: string): ParseResult => ({
  ok: false,
  code,
  error,
});

const normalizeHeader = (value: string): string =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9#]/g, '');

const columnFor = (value: string): KardexColumn | null =>
  normalizedAliases.get(normalizeHeader(value)) ?? null;

const headerColumns = (cells: string[]): Array<KardexColumn | null> | null => {
  const columns = cells.map(columnFor);
  const recognized = columns.filter((column) => column !== null);
  return recognized.length >= 3 && recognized.includes('code') ? columns : null;
};

const cellsForLine = (line: string): string[] =>
  line.includes('\t') ? line.split('\t') : line.trim().split(/\s{2,}/);

const unrecognized = (): ParseResult => failure(
  'unrecognized',
  'No se pudo reconocer el kardex en el PDF. Verifica que sea el reporte academico de SISS.',
);

export function parseKardexText(text: string): ParseResult {
  if (!text.trim()) return unrecognized();

  let columns: Array<KardexColumn | null> | null = null;
  const rows: Array<Record<string, string>> = [];

  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const cells = cellsForLine(line);
    const detectedHeader = headerColumns(cells);
    if (detectedHeader) {
      columns = detectedHeader;
      continue;
    }
    if (!columns) continue;

    const row: Record<string, string> = {};
    for (let index = 0; index < columns.length; index += 1) {
      const column = columns[index];
      const value = cells[index]?.trim();
      if (column && value) row[column] = value;
    }

    if (/^\d{4,12}$/.test(row.code ?? '')) rows.push(row);
  }

  if (rows.length === 0) return unrecognized();

  return {
    ok: true,
    kardex: normalizeAttempts(rows),
    rowCount: rows.length,
  };
}

const numericPosition = (item: PositionedTextItem, index: number): number | null => {
  const value = item.transform?.[index];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const groupPositionedLines = (
  items: PositionedTextItem[],
): Array<{ y: number; items: PositionedTextItem[] }> => {
  const groups = new Map<number, PositionedTextItem[]>();
  for (const item of items) {
    const y = numericPosition(item, 5);
    if (y === null || !item.str.trim()) continue;
    const key = Math.round(y * 2) / 2;
    const group = groups.get(key) ?? [];
    group.push(item);
    groups.set(key, group);
  }
  return [...groups.entries()]
    .map(([y, lineItems]) => ({
      y,
      items: lineItems.sort(
        (left, right) => (numericPosition(left, 4) ?? 0) - (numericPosition(right, 4) ?? 0),
      ),
    }))
    .sort((left, right) => right.y - left.y);
};

const anchorsFor = (items: PositionedTextItem[]): HeaderAnchor[] | null => {
  const anchors = items.flatMap((item) => {
    const x = numericPosition(item, 4);
    return x === null || !item.str.trim()
      ? []
      : [{ x, column: columnFor(item.str) }];
  });
  const recognized = anchors.flatMap(({ column }) => column ?? []);
  return recognized.length >= 3 && recognized.includes('code') ? anchors : null;
};

const nearestAnchor = (x: number, anchors: HeaderAnchor[]): number => {
  let nearest = 0;
  let distance = Number.POSITIVE_INFINITY;
  for (let index = 0; index < anchors.length; index += 1) {
    const candidate = Math.abs(x - anchors[index]!.x);
    if (candidate < distance) {
      nearest = index;
      distance = candidate;
    }
  }
  return nearest;
};

const positionedText = (items: PositionedTextItem[]): string | null => {
  const lines = groupPositionedLines(items);
  if (lines.length < 2) return null;

  let anchors: HeaderAnchor[] | null = null;
  const output: string[] = [];
  for (const line of lines) {
    const detected = anchorsFor(line.items);
    if (detected) {
      anchors = detected;
      output.push(line.items.map((item) => item.str.trim()).join('\t'));
      continue;
    }
    if (!anchors) continue;

    const cells = Array.from({ length: anchors.length }, () => '');
    for (const item of line.items) {
      const x = numericPosition(item, 4);
      const value = item.str.trim();
      if (x === null || !value) continue;
      const index = nearestAnchor(x, anchors);
      cells[index] = [cells[index], value].filter(Boolean).join(' ');
    }
    output.push(cells.join('\t'));
  }
  return output.length > 0 ? output.join('\n') : null;
};

const sequentialText = (items: PositionedTextItem[]): string => {
  let text = '';
  for (const item of items) {
    text += item.str;
    text += item.hasEOL ? '\n' : '\t';
  }
  return text;
};

const readFile = (file: File): Promise<ArrayBuffer> => {
  if (typeof file.arrayBuffer === 'function') return file.arrayBuffer();

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error('No se pudo leer el archivo.'));
    reader.onload = () => {
      if (reader.result instanceof ArrayBuffer) resolve(reader.result);
      else reject(new Error('No se pudo leer el archivo.'));
    };
    reader.readAsArrayBuffer(file);
  });
};

const hasPdfSignature = (bytes: ArrayBuffer): boolean => {
  const prefix = new Uint8Array(bytes, 0, Math.min(pdfSignature.length, bytes.byteLength));
  return String.fromCharCode(...prefix) === pdfSignature;
};

export async function parseKardexPdf(file: File): Promise<ParseResult> {
  if (file.size === 0) return failure('empty', 'El archivo esta vacio.');
  if (file.size > maximumPdfBytes) {
    return failure('too_large', 'El archivo supera el tamano maximo de 10 MB.');
  }
  if (file.type.toLowerCase() !== 'application/pdf') {
    return failure('invalid_type', 'Selecciona un archivo PDF.');
  }

  let bytes: ArrayBuffer;
  try {
    bytes = await readFile(file);
  } catch {
    return failure(
      'malformed',
      'No se pudo leer el PDF. Verifica que el archivo no este danado e intenta nuevamente.',
    );
  }

  if (!hasPdfSignature(bytes)) {
    return failure('invalid_signature', 'El archivo no es un PDF valido.');
  }

  try {
    const loadingTask = getDocument({ data: new Uint8Array(bytes) });
    try {
      const pdf = await loadingTask.promise;
      const pages: string[] = [];
      for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
        const page = await pdf.getPage(pageNumber);
        const content = await page.getTextContent();
        const items = content.items.filter(
          (item): item is typeof item & PositionedTextItem => 'str' in item,
        );
        pages.push(positionedText(items) ?? sequentialText(items));
      }
      return parseKardexText(pages.join('\n'));
    } finally {
      await loadingTask.destroy().catch(() => undefined);
    }
  } catch {
    return failure(
      'malformed',
      'No se pudo leer el PDF. Verifica que el archivo no este danado e intenta nuevamente.',
    );
  }
}
