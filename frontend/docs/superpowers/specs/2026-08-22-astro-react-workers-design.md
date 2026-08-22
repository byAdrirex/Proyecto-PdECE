# Migración del planificador académico a Astro + React en Cloudflare Workers

## Contexto y objetivo

El repositorio actual es una aplicación Flask/Jinja/HTMX que presenta la malla curricular de Economía UMSS, calcula estados académicos a partir de un Kardex, permite registrar materias y construye horarios con la oferta de la gestión 2026-2.

La migración debe vivir completamente en `frontend/`. Los archivos actuales (`app/`, `modulos/`, `tests/`, `datos/` y los entrypoints Python) no se modifican ni se usan como runtime de producción. El resultado será una aplicación Astro con componentes React, desplegable como Workers Static Assets mediante Wrangler en una URL temporal `workers.dev`.

## Decisión de arquitectura

Se usará Astro en modo estático y React para las islas interactivas. El Worker servirá los assets compilados; no se requiere Flask, un servidor Python, una base de datos, Durable Objects ni KV. Esta decisión mantiene el despliegue simple y coloca el trabajo pesado en el navegador, como pidió el usuario.

La aplicación tendrá ocho rutas públicas:

- `/` y `/malla`: malla curricular oficial y exploración de materias.
- `/guia`: información estática de la carrera.
- `/calendario-academico`: visor del PDF institucional.
- `/progreso`: registro de Kardex/manual y tablero de análisis.
- `/nuevo`: flujo de estudiante nuevo/restablecimiento local.
- `/horario`: selección de modo, Kardex, materias, grupos y resumen.
- `/horario/calendario`: calendario del horario seleccionado.

Las antiguas rutas HTMX se reemplazan por acciones locales de React. El estado de usuario se guarda en `localStorage` bajo una clave versionada; solo se persiste el Kardex normalizado, las trayectorias seleccionadas, el modo y el plan. El PDF original nunca se sube ni se publica.

## Componentes y límites

- `AppLayout.astro`: idioma, navegación, pie, estilos globales, ayuda de WhatsApp y captura de pantalla.
- `MallaExplorer.tsx`: malla, modal de materia, relaciones de prerrequisitos/dependientes, menciones/técnicos y estados visuales.
- `AcademicWorkspace.tsx`: estado persistente compartido y acciones de Kardex/progreso.
- `HorarioApp.tsx`: modos manual/académico, búsqueda, niveles, grupos, límites, conflictos, auxiliares, recomendaciones y resumen.
- `CalendarView.tsx`: eventos de clases/auxiliares y calendario semanal en español.
- `PdfViewer.tsx`: renderizado del calendario institucional con PDF.js.
- `src/lib/domain/`: reglas puras TypeScript para Kardex, motor académico, malla, oferta, objetivos, planificador y calendario.
- `src/data/`: JSON inmutable generado durante la migración desde el Excel y el PDF de oferta. No se incluyen PDFs personales.
- `scripts/`: herramientas de exportación/validación de fixtures y comprobaciones de paridad; no forman parte del bundle de Workers.

La interfaz conservará el contenido y comportamiento observable del Flask actual: materias, prerrequisitos, estados, progreso, menciones, técnicos, carga manual, importación de Kardex, límites de selección, advertencias, conflictos, recomendaciones, auxiliares y calendario.

## Datos y paridad

Los datos fijos del plan de estudios, prerrequisitos, objetivos y oferta se exportarán a JSON una sola vez. Los resultados de la aplicación Python se capturarán como fixtures dorados antes de retirar cualquier dependencia de runtime.

Los contratos mínimos de paridad son:

- 26 materias aprobadas para el Kardex de referencia, cuando se usa únicamente como fixture local de pruebas.
- 70 materias y 146 grupos para la oferta 2026-2.
- Mismos estados `APROBADA`, `REPROBADA`, `ABANDONADA`, `EN_CURSO`, `SIN_PRERREQUISITOS`, `DISPONIBLE` y `BLOQUEADA`.
- Mismos límites de gestión, detección de conflictos, horas semanales, recomendaciones y eventos de calendario.
- Mismos datos visibles en la malla, objetivos, materias dependientes y resumen de progreso.

La importación de Kardex usará PDF.js en el cliente y devolverá el mismo modelo normalizado que usa el dominio TypeScript. Si un PDF no puede reconocerse, se mantiene el flujo manual existente.

## Pruebas y validación

Se incorporarán Vitest para las reglas puras y fixtures de paridad, además de pruebas de interfaz para los flujos principales: abrir una materia, registrar Kardex manual, calcular progreso, seleccionar/quitar grupos, detectar conflicto y construir el calendario.

Antes de declarar terminado se ejecutará:

```text
npm run test
npm run check
npm run build
npx wrangler deploy --dry-run
```

El proyecto Python existente se usará como oráculo durante la migración, pero permanecerá fuera del build de `frontend/` y no se editará.

## Despliegue

`frontend/wrangler.jsonc` configurará el nombre temporal del Worker, la fecha de compatibilidad vigente y `assets.directory: ./dist`. `npm run deploy` compilará y ejecutará `wrangler deploy`; si Wrangler ya está autenticado, la entrega se hará en el subdominio `workers.dev`. El dominio propio se configurará después con `wrangler login`, `wrangler deploy` y la asociación de ruta/custom domain indicada en el instructivo final.

No habrá secretos ni variables sensibles en el bundle. El PDF personal de referencia y cualquier dato de estudiante se mantendrán fuera de `frontend/public/` y de los assets desplegados.

## Criterios de aceptación

1. `frontend/` contiene un proyecto Astro + React independiente y el código anterior conserva exactamente su estado.
2. `npm run check`, `npm run test` y `npm run build` terminan sin errores.
3. La malla, análisis, Kardex manual/PDF, planificador y calendario funcionan en navegador sin backend Python.
4. Los fixtures TypeScript coinciden con los resultados dorados del motor actual.
5. `wrangler deploy --dry-run` valida la configuración y el deploy temporal produce una URL `workers.dev` accesible.
6. La entrega incluye los comandos posteriores para autenticarse con Wrangler y conectar el dominio del usuario.
