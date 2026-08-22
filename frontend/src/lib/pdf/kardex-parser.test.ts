import { beforeEach, describe, expect, it, vi } from 'vitest';

import goldenKardex from '../../data/golden-kardex.json';
import { determineAttemptState } from '../domain/kardex';
import { createPlan } from '../domain/planner';
import {
  clearWorkspace,
  loadWorkspace,
  saveWorkspace,
  workspaceStorageKey,
  type WorkspaceState,
} from '../storage';
import { parseKardexPdf, parseKardexText } from './kardex-parser';

const pdfJs = vi.hoisted(() => ({
  getDocument: vi.fn(),
}));

vi.mock('./pdf-worker', () => ({
  getDocument: pdfJs.getDocument,
}));

const headers = [
  'Nro', 'Año', 'Gst', 'Código', 'Materia', 'Nv', 'Tp', 'Md', 'Cv', 'Gr', 'GrPr',
  'T1', 'T2', 'T3', 'P1', 'P2', 'EF', '2da', 'MdTl', 'EG', 'NFin', 'RFin',
];

const sanitizedKardexText = [
  headers.join('\t'),
  ...goldenKardex.subjects.map(({ code }, index) => [
    index + 1,
    2025,
    2,
    code,
    `MATERIA SANITIZADA ${index + 1}`,
    'A',
    '',
    'N',
    '',
    '',
    '',
    70,
    75,
    '',
    '',
    '',
    68,
    '',
    '',
    '',
    71,
    'APR',
  ].join('\t')),
].join('\n');

const emptyWorkspace: WorkspaceState = {
  version: 1,
  kardex: null,
  activeMentions: [],
  activeTechnicians: [],
  mode: null,
  plan: null,
};

const pdfFile = (contents: BlobPart, type = 'application/pdf'): File =>
  new File([contents], 'kardex.pdf', { type });

const textItem = (str: string) => ({
  str,
  dir: 'ltr',
  transform: [1, 0, 0, 1, 0, 0],
  width: str.length,
  height: 10,
  fontName: 'sans-serif',
  hasEOL: true,
});

describe('workspace storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('migrates an empty browser state to the current workspace version', () => {
    expect(loadWorkspace()).toEqual(emptyWorkspace);
  });

  it('round-trips only normalized workspace JSON', () => {
    const parsed = parseKardexText(sanitizedKardexText);
    const workspace: WorkspaceState = {
      version: 1,
      kardex: parsed.ok ? parsed.kardex : null,
      activeMentions: ['mencion-financiera'],
      activeTechnicians: ['tecnico-datos'],
      mode: 'academic',
      plan: createPlan('academic', 2026, 2),
    };

    saveWorkspace(workspace);

    expect(loadWorkspace()).toEqual(workspace);
    expect(JSON.parse(localStorage.getItem(workspaceStorageKey) ?? '')).toEqual(workspace);

    clearWorkspace();
    expect(localStorage.getItem(workspaceStorageKey)).toBeNull();
  });

  it('recovers from invalid JSON without retaining the corrupt value', () => {
    localStorage.setItem(workspaceStorageKey, '{not-json');

    expect(loadWorkspace()).toEqual(emptyWorkspace);
    expect(localStorage.getItem(workspaceStorageKey)).toBeNull();
  });

  it('rejects and removes an unsupported workspace version', () => {
    localStorage.setItem(workspaceStorageKey, JSON.stringify({
      ...emptyWorkspace,
      version: 2,
    }));

    expect(loadWorkspace()).toEqual(emptyWorkspace);
    expect(localStorage.getItem(workspaceStorageKey)).toBeNull();
  });

  it('rejects and removes valid JSON containing an incomplete planner plan', () => {
    localStorage.setItem(workspaceStorageKey, JSON.stringify({
      ...emptyWorkspace,
      mode: 'academic',
      plan: { mode: 'academic' },
    }));

    expect(loadWorkspace()).toEqual(emptyWorkspace);
    expect(localStorage.getItem(workspaceStorageKey)).toBeNull();
  });

  it('rejects and removes a persisted Kardex with an incomplete attempt', () => {
    localStorage.setItem(workspaceStorageKey, JSON.stringify({
      ...emptyWorkspace,
      kardex: {
        attempts: { '1304001': [{ result: 'APR' }] },
        currentYear: 2026,
        currentTerm: 2,
      },
    }));

    expect(loadWorkspace()).toEqual(emptyWorkspace);
    expect(localStorage.getItem(workspaceStorageKey)).toBeNull();
  });
});

describe('Kardex text parsing', () => {
  it('marks an ungraded attempt in the current 2026/2 offer as in progress', () => {
    const currentRow = [
      1, 2026, 2, '1304099', 'MATERIA EN CURSO', 'I', '', 'N', '', '', '',
      70, 75, '', '', '', '', '', '', '', '', '',
    ].join('\t');

    const parsed = parseKardexText([headers.join('\t'), currentRow].join('\n'));

    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.kardex).toMatchObject({ currentYear: 2026, currentTerm: 2 });
    expect(determineAttemptState(parsed.kardex.attempts['1304099'], {
      year: parsed.kardex.currentYear,
      term: parsed.kardex.currentTerm,
    })).toMatchObject({ status: 'EN_CURSO', provisional: true });
  });

  it('normalizes the sanitized SISS rows and preserves golden aggregate parity', () => {
    const result = parseKardexText(sanitizedKardexText);

    expect(result.ok).toBe(true);
    if (!result.ok) return;

    expect(result.rowCount).toBe(goldenKardex.subjectCount);
    expect(Object.keys(result.kardex.attempts)).toEqual(
      goldenKardex.subjects.map(({ code }) => code),
    );
    expect(
      Object.values(result.kardex.attempts)
        .filter((attempts) => attempts.some((attempt) => attempt.result === 'APR')),
    ).toHaveLength(goldenKardex.approved);
    expect(result.kardex.attempts['1304001']?.[0]).toMatchObject({
      year: 2025,
      term: 2,
      final: 71,
      result: 'APR',
      mode: 'N',
      modality: 'Normal',
      period: 'semestre regular 2',
      exam: 68,
    });
  });

  it('returns the manual-flow fallback for unrecognized text', () => {
    expect(parseKardexText('Documento sin una tabla academica')).toEqual({
      ok: false,
      code: 'unrecognized',
      error: 'No se pudo reconocer el kardex en el PDF. Verifica que sea el reporte academico de SISS.',
    });
  });
});

describe('PDF file validation and extraction', () => {
  beforeEach(() => {
    pdfJs.getDocument.mockReset();
  });

  it('rejects an empty PDF', async () => {
    await expect(parseKardexPdf(pdfFile(''))).resolves.toEqual({
      ok: false,
      code: 'empty',
      error: 'El archivo esta vacio.',
    });
  });

  it('rejects a PDF larger than 10 MiB', async () => {
    const oversized = pdfFile(new Uint8Array((10 * 1024 * 1024) + 1));

    await expect(parseKardexPdf(oversized)).resolves.toEqual({
      ok: false,
      code: 'too_large',
      error: 'El archivo supera el tamano maximo de 10 MB.',
    });
  });

  it('rejects a file whose MIME type is not PDF', async () => {
    await expect(parseKardexPdf(pdfFile('%PDF-1.7', 'text/plain'))).resolves.toEqual({
      ok: false,
      code: 'invalid_type',
      error: 'Selecciona un archivo PDF.',
    });
  });

  it('rejects a PDF MIME type with a non-PDF signature', async () => {
    await expect(parseKardexPdf(pdfFile('not a pdf'))).resolves.toEqual({
      ok: false,
      code: 'invalid_signature',
      error: 'El archivo no es un PDF valido.',
    });
  });

  it('returns an actionable error when PDF.js cannot read the document', async () => {
    pdfJs.getDocument.mockReturnValue({
      promise: Promise.reject(new Error('Invalid PDF structure')),
      destroy: vi.fn().mockResolvedValue(undefined),
    });

    await expect(parseKardexPdf(pdfFile('%PDF-1.7'))).resolves.toEqual({
      ok: false,
      code: 'malformed',
      error: 'No se pudo leer el PDF. Verifica que el archivo no este danado e intenta nuevamente.',
    });
  });

  it('returns the same actionable error when PDF.js initialization throws', async () => {
    pdfJs.getDocument.mockImplementation(() => {
      throw new Error('Worker initialization failed');
    });

    await expect(parseKardexPdf(pdfFile('%PDF-1.7'))).resolves.toEqual({
      ok: false,
      code: 'malformed',
      error: 'No se pudo leer el PDF. Verifica que el archivo no este danado e intenta nuevamente.',
    });
  });

  it('forwards a caller-supplied active period through PDF extraction', async () => {
    pdfJs.getDocument.mockReturnValue({
      promise: Promise.resolve({
        numPages: 1,
        getPage: vi.fn().mockResolvedValue({
          getTextContent: vi.fn().mockResolvedValue({
            items: sanitizedKardexText.split('\n').map(textItem),
            styles: {},
            lang: null,
          }),
        }),
      }),
      destroy: vi.fn().mockResolvedValue(undefined),
    });

    const result = await parseKardexPdf(
      pdfFile('%PDF-1.7'),
      { currentYear: 2027, currentTerm: 1 },
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.kardex).toMatchObject({ currentYear: 2027, currentTerm: 1 });
    }
  });

  it('extracts text locally with PDF.js and never sends the File over the network', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    pdfJs.getDocument.mockReturnValue({
      promise: Promise.resolve({
        numPages: 1,
        getPage: vi.fn().mockResolvedValue({
          getTextContent: vi.fn().mockResolvedValue({
            items: sanitizedKardexText.split('\n').map(textItem),
            styles: {},
            lang: null,
          }),
        }),
      }),
      destroy: vi.fn().mockResolvedValue(undefined),
    });

    const result = await parseKardexPdf(pdfFile('%PDF-1.7'));

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.rowCount).toBe(goldenKardex.subjectCount);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
