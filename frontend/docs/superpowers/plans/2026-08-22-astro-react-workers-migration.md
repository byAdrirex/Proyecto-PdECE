# Astro React Workers Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build an independent Astro + React frontend in frontend/ that reproduces the current academic malla, analysis, Kardex and schedule planner in the browser and deploys as Cloudflare Workers Static Assets.

**Architecture:** Astro serves static route shells and React islands own all interactive state. Immutable JSON generated from the current Python engine supplies the curriculum, objectives, prerequisites and 2026-2 offer; normalized Kardex and planner state stay in versioned local storage. No existing Python file is edited or imported at runtime.

**Tech Stack:** Astro 6, React 19, TypeScript strict, Vite, Vitest, Playwright, PDF.js, FullCalendar, html2canvas, Wrangler 4, Cloudflare Workers Static Assets.

**Spec:** frontend/docs/superpowers/specs/2026-08-22-astro-react-workers-design.md

## Global Constraints

- All migration code and generated frontend data live under frontend/.
- Do not modify app/, modulos/, tests/, datos/, main.py, or requirements.txt.
- Do not publish datos/webSISS Sistema de Información San Simón.pdf or any personal Kardex.
- The public behavior remains Spanish and preserves malla, analysis, Kardex, planner, conflicts, recommendations, auxiliaries and calendar results.
- User state is local-only and versioned; no backend session, database, KV or Durable Object is required.
- Every new domain rule is implemented test-first: write a failing Vitest test, observe the expected failure, implement the smallest passing rule, then refactor.
- npm run check, npm run test, npm run build, and npx wrangler deploy --dry-run must pass before deployment.

---

### Task 1: Scaffold the isolated Astro/React/Workers project

**Files:**
- Create: frontend/package.json
- Create: frontend/astro.config.mjs
- Create: frontend/tsconfig.json
- Create: frontend/vite.config.ts
- Create: frontend/wrangler.jsonc
- Create: frontend/.gitignore
- Create: frontend/src/env.d.ts
- Create: frontend/src/pages/index.astro
- Create: frontend/src/layouts/AppLayout.astro
- Create: frontend/src/styles/global.css

**Interfaces:**
- Produces npm scripts dev, check, test, test:watch, build, preview, deploy and deploy:dry used by later tasks.
- Produces an Astro static build whose only deploy asset directory is frontend/dist.

- [ ] Step 1: Write the scaffold verification test

Create frontend/tests/scaffold.test.ts:

~~~ts
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = resolve(import.meta.dirname, '..');

describe('frontend scaffold', () => {
  it('declares Astro, React and Workers scripts', () => {
    const pkg = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8')) as {
      scripts: Record<string, string>;
      dependencies: Record<string, string>;
    };
    expect(pkg.scripts.build).toContain('astro build');
    expect(pkg.scripts.deploy).toContain('wrangler deploy');
    expect(pkg.dependencies.astro).toBeTruthy();
    expect(pkg.dependencies.react).toBeTruthy();
  });

  it('keeps Worker assets pointed at dist', () => {
    const config = readFileSync(resolve(root, 'wrangler.jsonc'), 'utf8');
    expect(config).toContain('"directory": "./dist"');
    expect(config).not.toContain('webSISS');
  });
});
~~~

- [ ] Step 2: Run the test to verify the scaffold is absent

Run from frontend/: npm test -- --run tests/scaffold.test.ts

Expected: FAIL because the new frontend package and configuration do not exist yet.

- [ ] Step 3: Generate the Astro scaffold and install runtime tools

Run from the repository root:

~~~powershell
New-Item -ItemType Directory -Force -Path frontend | Out-Null
Set-Location frontend
npm create astro@latest . -- --template minimal --install --no-git
npm install @astrojs/react react react-dom pdfjs-dist @fullcalendar/core @fullcalendar/daygrid @fullcalendar/timegrid @fullcalendar/interaction html2canvas
npm install -D @astrojs/check @types/react @types/react-dom typescript vitest @vitest/coverage-v8 jsdom wrangler
~~~

Configure astro.config.mjs with output: 'static' and the React integration. Configure Vitest with environment: 'jsdom' and include patterns for tests/**/*.test.ts and src/**/*.test.ts. Set strict TypeScript compiler options in tsconfig.json.

Create wrangler.jsonc with the current compatibility date, name planificador-academico-umss-temp, and:

~~~jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "planificador-academico-umss-temp",
  "compatibility_date": "2026-08-22",
  "assets": {
    "directory": "./dist",
    "not_found_handling": "404-page"
  }
}
~~~

Define deploy as npm run build && wrangler deploy, deploy:dry as npm run build && wrangler deploy --dry-run, and exclude dist/, .astro/, .wrangler/, node_modules/, .env*, and local generated PDFs from .gitignore.

- [ ] Step 4: Run the scaffold test to verify it passes

Run: npm test -- --run tests/scaffold.test.ts

Expected: PASS.

- [ ] Step 5: Run the generated project check

Run: npm run check

Expected: exit code 0 with no TypeScript or Astro diagnostics.

- [ ] Step 6: Commit the isolated scaffold

~~~powershell
git add frontend
git commit -m "feat: scaffold Astro React Workers frontend"
~~~

### Task 2: Export immutable academic fixtures without changing the Python app

**Files:**
- Create: frontend/scripts/export-fixtures.py
- Create: frontend/src/data/catalog.json
- Create: frontend/src/data/objectives.json
- Create: frontend/src/data/offer.json
- Create: frontend/src/data/golden-kardex.json
- Create: frontend/src/data/golden-results.json
- Create: frontend/src/data/README.md
- Test: frontend/tests/fixtures.test.ts

**Interfaces:**
- catalog.json contains typed subject records, prerequisite/dependent edges, levels, areas, credits, hours and type.
- objectives.json contains the six trajectories and substitution data used by the malla.
- offer.json contains the 2026-2 group records, schedule blocks and auxiliary blocks indexed by SIS code.
- golden-results.json records parity counts and representative outputs consumed by domain tests.

- [ ] Step 1: Write the failing fixture contract test

Create frontend/tests/fixtures.test.ts asserting the exact minimum shape and counts:

~~~ts
import catalog from '../src/data/catalog.json';
import offer from '../src/data/offer.json';
import golden from '../src/data/golden-results.json';
import { describe, expect, it } from 'vitest';

describe('academic fixtures', () => {
  it('contains the official curriculum and offer', () => {
    expect(catalog.subjects.length).toBeGreaterThan(0);
    expect(offer.totalSubjects).toBe(70);
    expect(offer.totalGroups).toBe(146);
  });

  it('records the Python oracle counts', () => {
    expect(golden.kardex.approved).toBe(26);
    expect(golden.offer.subjects).toBe(70);
    expect(golden.offer.groups).toBe(146);
  });
});
~~~

- [ ] Step 2: Run the test to verify fixtures are absent

Run: npm test -- --run tests/fixtures.test.ts

Expected: FAIL because the generated JSON files do not exist.

- [ ] Step 3: Generate fixtures with a new script that imports existing modules read-only

Implement export-fixtures.py under frontend/scripts/. It adds the repository modulos directory to sys.path, calls the existing loaders, serializes only public curriculum/offer/objective structures, processes the reference Kardex into a normalized JSON fixture, and writes only under frontend/src/data/. It must skip the personal PDF from any public directory and record only aggregate golden counts plus sanitized subject-level attempts needed by tests.

Run it with the project interpreter:

~~~powershell
..\\venv\\Scripts\\python.exe scripts\\export-fixtures.py
~~~

If the local interpreter is unavailable, use the bundled Python runtime with the repository root on PYTHONPATH; do not install or modify dependencies in the existing project.

- [ ] Step 4: Validate fixture contents and forbidden-file exclusion

Run:

~~~powershell
npm test -- --run tests/fixtures.test.ts
if (rg -n "webSISS|Sistema de Información" src public dist) { throw "personal Kardex leaked into frontend" }
~~~

Expected: PASS and no forbidden personal-file match.

- [ ] Step 5: Commit the normalized data

~~~powershell
git add frontend/src/data frontend/scripts/export-fixtures.py frontend/tests/fixtures.test.ts
git commit -m "feat: add normalized academic fixtures"
~~~

### Task 3: Port the academic domain with test-first parity

**Files:**
- Create: frontend/src/lib/domain/types.ts
- Create: frontend/src/lib/domain/kardex.ts
- Create: frontend/src/lib/domain/academic.ts
- Create: frontend/src/lib/domain/curriculum.ts
- Create: frontend/src/lib/domain/objectives.ts
- Create: frontend/src/lib/domain/kardex.test.ts
- Create: frontend/src/lib/domain/academic.test.ts
- Create: frontend/src/lib/domain/curriculum.test.ts
- Create: frontend/src/lib/domain/objectives.test.ts

**Interfaces:**
- KardexState, Attempt, Subject, OfferGroup, Objective, AcademicState and MallaModel are defined in types.ts and reused by React.
- normalizeAttempts(input), determineAttemptState(attempts), subjectState(code, catalog, kardex, offer), progressSummary(...), buildMallaModel(...) and applyObjectiveSelections(...) are pure functions with no DOM, storage or network access.

- [ ] Step 1: Write failing Kardex tests

Cover normalization, latest-attempt selection, approval, failure, course-in-progress, historical approval after a later failure, and grade ranges. Example:

~~~ts
it('keeps a historical approval when a later attempt fails', () => {
  const result = determineAttemptState({
    '1304001': {
      attempts: [
        { year: 2025, term: 1, final: 65, result: 'APR' },
        { year: 2026, term: 1, final: 40, result: 'REP' }
      ]
    }
  });
  expect(result.status).toBe('APROBADA');
  expect(result.provisional).toBe(true);
});
~~~

- [ ] Step 2: Run the Kardex tests and observe the expected failure

Run: npm test -- --run src/lib/domain/kardex.test.ts

Expected: FAIL with missing module/function errors.

- [ ] Step 3: Implement the minimal typed Kardex rules

Port the rules used by importador_kardex.py and procesador_kardex.py without retaining pandas-shaped data. Preserve numeric grades, period/mode fields, repeated-attempt semantics, and the exact visible status labels.

- [ ] Step 4: Run Kardex tests and refactor only after green

Run the targeted test, then npm test -- --run src/lib/domain/kardex.test.ts src/lib/domain/academic.test.ts after adding academic rules. Expected: all targeted tests pass with no warnings.

- [ ] Step 5: Write failing academic/curriculum/objective tests

Cover prerequisite states, offered/not-offered states, missing prerequisites, progress percentages, credits, malla cells by semester/area, dependents, active mentions, active technicians, substitution colors and elective totals. Assert representative golden results rather than implementation details.

- [ ] Step 6: Implement pure academic selectors and malla model builders

Use imported JSON fixtures as immutable inputs. Port only the web-used rules from motor_academico.py, malla.py, objetivos.py and prerrequisitos.py; do not port pandas, file I/O, print helpers or legacy duplicate Kardex models.

- [ ] Step 7: Run all domain tests and verify parity

Run: npm test -- --run src/lib/domain

Expected: PASS; aggregate results match the Python oracle fixture.

- [ ] Step 8: Commit the domain layer

~~~powershell
git add frontend/src/lib/domain
git commit -m "feat: port academic domain to TypeScript"
~~~

### Task 4: Port planner, conflicts and calendar rules with tests first

**Files:**
- Create: frontend/src/lib/domain/planner.ts
- Create: frontend/src/lib/domain/calendar.ts
- Create: frontend/src/lib/domain/planner.test.ts
- Create: frontend/src/lib/domain/calendar.test.ts

**Interfaces:**
- createPlan(mode, year, term), selectGroup(plan, group, context), removeGroup(plan, code, groupNumber), limits(plan), detectConflicts(plan, includeAuxiliary), recommendGroup(group, plan, academic), weeklyHours(plan), calendarEvents(plan, term) and planSummary(plan) are pure functions.

- [ ] Step 1: Write failing tests for limits, duplicates and conflicts

Assert regular limits (8 normal/2 mesa), intersemester limits (2 and no mesa), same-group duplicate rejection, overlapping class/auxiliary blocks, academic blocked/approved rejection, manual warnings, recommendation scores and removal.

- [ ] Step 2: Run targeted tests to verify failure

Run: npm test -- --run src/lib/domain/planner.test.ts

Expected: FAIL because planner functions do not exist.

- [ ] Step 3: Implement minimal planner rules

Translate the comparison and ordering behavior from modulos/planificador.py, including LU-SA ordering, time overlap, warning messages and selection object shape. Keep conflicts selectable exactly as in the current UI while reporting them in the plan summary.

- [ ] Step 4: Write failing calendar tests and implement event generation

Assert Monday-Saturday events, class/auxiliary distinction, 2026-08-17 through 2026-12-19 recurrence metadata, pastel group colors and red conflict blocks.

- [ ] Step 5: Run planner and calendar tests

Run: npm test -- --run src/lib/domain/planner.test.ts src/lib/domain/calendar.test.ts

Expected: PASS with no console warnings.

- [ ] Step 6: Commit planner and calendar rules

~~~powershell
git add frontend/src/lib/domain/planner.ts frontend/src/lib/domain/calendar.ts frontend/src/lib/domain/planner.test.ts frontend/src/lib/domain/calendar.test.ts
git commit -m "feat: port planner and calendar rules"
~~~

### Task 5: Add local persistence and PDF Kardex parsing

**Files:**
- Create: frontend/src/lib/storage.ts
- Create: frontend/src/lib/pdf/kardex-parser.ts
- Create: frontend/src/lib/pdf/kardex-parser.test.ts
- Create: frontend/src/lib/pdf/pdf-worker.ts

**Interfaces:**
- loadWorkspace(), saveWorkspace(workspace), clearWorkspace(), workspaceStorageKey and WorkspaceState isolate local persistence.
- parseKardexPdf(file): Promise<ParseResult> validates PDF type/signature and 10 MiB maximum, extracts PDF.js text, parses rows and returns typed Kardex data or actionable errors.

- [ ] Step 1: Write failing storage and parser tests

Test versioned storage migration from empty state, round-trip serialization, invalid JSON recovery, PDF size/type/signature rejection and sanitized sample text parsing. Keep a text fixture rather than bundling the personal PDF.

- [ ] Step 2: Run tests to observe failure

Run: npm test -- --run src/lib/pdf/kardex-parser.test.ts

Expected: FAIL because storage and parser modules do not exist.

- [ ] Step 3: Implement storage and PDF.js parsing

Use browser localStorage only for normalized JSON. Configure the PDF.js worker URL through an imported asset. Never send the File to fetch, a Worker endpoint or analytics. Preserve current fallback messages for empty, malformed and unrecognized PDFs.

- [ ] Step 4: Run parser tests and compare the normalized sample fixture

Run: npm test -- --run src/lib/pdf/kardex-parser.test.ts

Expected: PASS; normalized rows and the 26-approved aggregate match golden-kardex.json.

- [ ] Step 5: Commit local state and PDF parsing

~~~powershell
git add frontend/src/lib/storage.ts frontend/src/lib/pdf
git commit -m "feat: add local workspace and Kardex PDF parser"
~~~

### Task 6: Build React islands and Astro pages

**Files:**
- Create: frontend/src/components/MallaExplorer.tsx
- Create: frontend/src/components/AcademicWorkspace.tsx
- Create: frontend/src/components/HorarioApp.tsx
- Create: frontend/src/components/CalendarView.tsx
- Create: frontend/src/components/PdfViewer.tsx
- Create: frontend/src/components/ui/*.tsx
- Modify: frontend/src/layouts/AppLayout.astro
- Modify: frontend/src/pages/index.astro
- Create: frontend/src/pages/malla.astro
- Create: frontend/src/pages/guia.astro
- Create: frontend/src/pages/calendario-academico.astro
- Create: frontend/src/pages/progreso.astro
- Create: frontend/src/pages/nuevo.astro
- Create: frontend/src/pages/horario.astro
- Create: frontend/src/pages/horario/calendario.astro
- Modify: frontend/src/styles/global.css

**Interfaces:**
- Components consume only typed domain functions, fixture JSON and WorkspaceState.
- MallaExplorer accepts showBackLink?: boolean; HorarioApp accepts calendarOnly?: boolean; AcademicWorkspace exposes the same state to progress and planner routes through local storage.

- [ ] Step 1: Write failing component tests for critical flows

Create React tests for opening a subject modal, adding/removing a manual Kardex subject, showing progress, selecting a group, reporting a conflict and rendering calendar event labels. Use real domain functions and fixture data; mock only browser APIs such as localStorage, PDF.js and canvas.

- [ ] Step 2: Run component tests to verify failure

Run: npm test -- --run src/components

Expected: FAIL because React components and route shells do not exist.

- [ ] Step 3: Implement shared layout and static Astro pages

Port Spanish titles, navigation, footer, WhatsApp help link, screenshot action, print rules, guide accordions, institutional PDF fallback and route-specific links. Keep all external links noopener noreferrer and do not copy personal source files into public/.

- [ ] Step 4: Implement MallaExplorer

Render the nine-semester official grid, areas, workshops/English, status legend, objective cards and subject dialog. Preserve mobile horizontal scrolling, relation highlighting, prerequisite/dependent lists, active trajectory toggles and local persistence.

- [ ] Step 5: Implement AcademicWorkspace and HorarioApp

Implement mode selection, PDF/manual Kardex flows, materia search, level accordions, group cards, limits, warnings, auxiliary toggle, selection/removal, sidebar summary and links between progress/malla/planner. Refresh derived summary and calendar without full-page reload.

- [ ] Step 6: Implement CalendarView and PdfViewer

Bundle FullCalendar plugins and PDF.js. Configure Spanish labels, Monday-Saturday grid, 06:45-21:45 range, 90-minute slots, responsive overflow, group colors and conflict coloring.

- [ ] Step 7: Run component tests and build

Run: npm test -- --run src/components && npm run check && npm run build

Expected: PASS and a frontend/dist directory containing only frontend assets.

- [ ] Step 8: Commit the UI and routes

~~~powershell
git add frontend/src
git commit -m "feat: build Astro React academic planner UI"
~~~

### Task 7: End-to-end verification and Workers deployment

**Files:**
- Create: frontend/tests/e2e/malla.spec.ts
- Create: frontend/tests/e2e/planner.spec.ts
- Create: frontend/public/404.html
- Modify: frontend/package.json
- Modify: frontend/wrangler.jsonc
- Create: frontend/README.md

**Interfaces:**
- E2E tests start the built static site locally and exercise the same URLs users receive from Workers.
- README documents local development, temporary deploy, Wrangler login, custom domain and data privacy.

- [ ] Step 1: Write E2E tests before final deployment changes

malla.spec.ts opens /, clicks ECONOMIA GENERAL, verifies its prerequisite/dependent dialog and navigates to /guia. planner.spec.ts opens /horario, chooses manual mode, adds a known course, selects a group, verifies the sidebar and opens /horario/calendario.

- [ ] Step 2: Run E2E tests against the current build and observe missing behavior

Run npm run build; start npx astro preview --host 127.0.0.1 --port 4321 in one terminal and run npx playwright test in another.

Expected initially: failures identify incomplete route or island behavior; fix implementation, not test expectations.

- [ ] Step 3: Run the complete local verification suite

From frontend/ run:

~~~powershell
npm run test
npm run check
npm run build
npx wrangler deploy --dry-run
~~~

Expected: all Vitest/E2E tests pass, Astro check is clean, build exits 0, and Wrangler validates assets.directory without listing personal files.

- [ ] Step 4: Deploy to the temporary Workers URL

Run npm run deploy. If Wrangler reports missing authentication, run npx wrangler whoami and report the exact login requirement rather than fabricating a URL. When authenticated, capture the returned workers.dev URL and smoke-test /, /malla, /progreso, /horario and /calendario-academico.

- [ ] Step 5: Document the handoff

Write frontend/README.md with:

~~~text
npm install
npm run dev
npm run test
npm run build
npm run deploy
npx wrangler login
npx wrangler deploy
~~~

Explain how to attach the existing domain through Cloudflare Workers custom domains/routes, how to select the production Worker name, and that user Kardex data remains local to the browser.

- [ ] Step 6: Commit verified frontend and deployment docs

~~~powershell
git add frontend
git commit -m "feat: prepare Astro React frontend for Workers deployment"
~~~

