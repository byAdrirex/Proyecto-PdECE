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
