/**
 * Process-wide database isolation for every `bun test` invocation.
 *
 * Unit tests are hermetic by default: inherited Postgres routes are removed
 * before test modules import engine/config code. Container-backed E2E must opt
 * in explicitly, but production-shaped routes remain forbidden even then.
 */

export const TEST_DATABASE_OPT_IN = 'GBRAIN_TEST_ALLOW_DATABASE';

export function isForbiddenTestDatabaseRoute(value: string): boolean {
  try {
    const url = new URL(value);
    const protocol = url.protocol.toLowerCase();
    if (protocol !== 'postgres:' && protocol !== 'postgresql:') return true;

    const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, '');
    if (host !== '127.0.0.1' && host !== 'localhost' && host !== '::1') return true;
    if (host === '127.0.0.1' && url.port === '6432') return true;
    if (host === 'localhost' && url.port === '6432') return true;
    if (host === '::1' && url.port === '6432') return true;
    return false;
  } catch {
    return true;
  }
}

export function applyTestDatabaseRouteGuard(
  env: Record<string, string | undefined> = process.env,
): void {
  const routes = [env.GBRAIN_DATABASE_URL, env.DATABASE_URL].filter(
    (value): value is string => Boolean(value),
  );

  const optedIn = env[TEST_DATABASE_OPT_IN] === '1';
  if (!optedIn) {
    delete env.GBRAIN_DATABASE_URL;
    delete env.DATABASE_URL;
    return;
  }

  if (routes.length === 0) {
    throw new Error(
      `${TEST_DATABASE_OPT_IN}=1 requires an explicit isolated DATABASE_URL`,
    );
  }

  if (routes.some(isForbiddenTestDatabaseRoute)) {
    throw new Error(
      'Refusing test startup with a production-shaped or invalid database route',
    );
  }
}

applyTestDatabaseRouteGuard();
