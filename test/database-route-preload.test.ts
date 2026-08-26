import { describe, expect, test } from 'bun:test';
import { readFileSync } from 'node:fs';
import {
  applyTestDatabaseRouteGuard,
  isForbiddenTestDatabaseRoute,
  TEST_DATABASE_OPT_IN,
} from './helpers/database-route-preload.ts';

describe('test database route preload', () => {
  test('is wired as the first Bun test preload', () => {
    const bunfig = readFileSync(new URL('../bunfig.toml', import.meta.url), 'utf8');
    const routeGuard = bunfig.indexOf('./test/helpers/database-route-preload.ts');
    const embeddingPreload = bunfig.indexOf('./test/helpers/legacy-embedding-preload.ts');

    expect(routeGuard).toBeGreaterThan(-1);
    expect(embeddingPreload).toBeGreaterThan(routeGuard);
  });

  test('clears inherited database routes without an explicit E2E opt-in', () => {
    const env: Record<string, string | undefined> = {
      DATABASE_URL: 'postgresql://test:test@127.0.0.1:55432/test',
      GBRAIN_DATABASE_URL: 'postgresql://test:test@localhost:55432/test',
    };

    applyTestDatabaseRouteGuard(env);

    expect(env.DATABASE_URL).toBeUndefined();
    expect(env.GBRAIN_DATABASE_URL).toBeUndefined();
  });

  test('permits only an explicitly opted-in isolated Postgres route', () => {
    const env: Record<string, string | undefined> = {
      [TEST_DATABASE_OPT_IN]: '1',
      DATABASE_URL: 'postgresql://test:test@127.0.0.1:55432/test',
    };

    applyTestDatabaseRouteGuard(env);

    expect(env.DATABASE_URL).toBe('postgresql://test:test@127.0.0.1:55432/test');
  });

  test('fails closed when database opt-in has no isolated route', () => {
    const env: Record<string, string | undefined> = {
      [TEST_DATABASE_OPT_IN]: '1',
    };

    expect(() => applyTestDatabaseRouteGuard(env)).toThrow(
      'requires an explicit isolated DATABASE_URL',
    );
  });

  test.each([
    'postgresql://postgres@127.0.0.1:6432/postgres',
    'postgresql://postgres@localhost:6432/postgres',
    'postgresql://postgres@[::1]:6432/postgres',
    'postgresql://postgres@db.example.supabase.co:5432/postgres',
    'postgresql://postgres@aws-0.example.pooler.supabase.com:6543/postgres',
    'postgresql://postgres@db.internal.example:5432/postgres',
  ])('refuses production-shaped route %s even with the E2E opt-in', (route) => {
    expect(isForbiddenTestDatabaseRoute(route)).toBe(true);
    const env: Record<string, string | undefined> = {
      [TEST_DATABASE_OPT_IN]: '1',
      DATABASE_URL: route,
    };

    expect(() => applyTestDatabaseRouteGuard(env)).toThrow(
      'Refusing test startup',
    );
  });
});
