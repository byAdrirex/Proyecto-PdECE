# Academic fixtures

These immutable JSON files are generated at build time by
`frontend/scripts/export-fixtures.py` from the existing local academic loaders.
They are browser-safe inputs for the TypeScript domain layer; the frontend does
not execute Python or access source documents at runtime.

`golden-kardex.json` is intentionally sanitized. It preserves only SIS subject
codes and final result labels needed for parity tests, plus aggregate counts.
It excludes student identity, raw document contents, dates, grades, page
metadata, and other source fields.
